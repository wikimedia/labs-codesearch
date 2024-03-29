/**
 * Copyright (C) 2022 Timo Tijhof
 * Copyright (C) 2020 Kunal Mehta <legoktm@debian.org>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

import { select, dom, isEmpty, now } from './util.js';
import * as view from './view.js';

const OFFSET_INTIAL = false;
const OFFSET_MORE = true;

function formatApiQueryUrl( apiQueryUrl, repos = '*', mode = OFFSET_INTIAL ) {
	const apiUrl = new URL( apiQueryUrl );

	apiUrl.searchParams.set( 'repos', repos );

	if ( mode === OFFSET_INTIAL ) {
		apiUrl.searchParams.set( 'rng', ':20' );
	} else {
		// "Load more" pagination, get remaining results for the given repo.
		apiUrl.searchParams.set( 'rng', '20:' );
	}

	return apiUrl.toString();
}

async function fetchResults( apiQueryUrl ) {
	// Optimization: This fetch starts preloaded in templates/index.mustache.
	const apiResp = await fetch( apiQueryUrl, { mode: 'cors' } );
	try {
		// Streams may only be consumed once. In order for the catch to be able
		// to read it as text(), we must clone() here before calling json().
		// https://stackoverflow.com/q/74346746/319266
		// https://developer.mozilla.org/en-US/docs/Web/API/Response/clone
		return await apiResp.clone().json();
	} catch ( err ) {
		// eslint-disable-next-line no-console
		console.error( err );

		// If the response is not JSON, assume this is a plain text error
		// from our app.py proxy, rather than a Hound API response.
		return {
			Error: ( await apiResp.text() ).slice(0, 1024)
		};
	}
}

function renderResponse( repos, apiData, queryState, rerenderFn, loadFn ) {
	if ( !repos || isEmpty( repos ) ) {
		return view.buildError( new Error( 'Failed to fetch repository metadata' ) );
	}
	if ( apiData.Error ) {
		// This is either:
		// - a Hound API response, where it responds with `{"Error":…}`.
		// - a simulated error from fetchResults(), in which case it's usually
		//   a plain text response from our app.py proxy,
		//   which fetchResults() converts to the same format.
		return view.buildError( apiData.Error );
	}

	if ( isEmpty( apiData.Results ) ) {
		return dom( 'div', {
			className: 'alert alert-primary',
			role: 'alert'
		}, [ 'No results found.' ] );
	}

	try {
		const formatted = document.createDocumentFragment();
		formatted.append( view.buildFormatNav( repos, apiData, queryState, rerenderFn ) );
		switch ( queryState.format ) {
			case 'Default':
				formatted.append( view.buildResultsDefault( repos, apiData.Results, queryState, loadFn ) );
				break;
			case 'Phabricator':
				formatted.append( view.buildResultsPhabricator( repos, apiData.Results, queryState ) );
				break;
			default:
				throw new Error( 'Unknown result format' );
		}
		return formatted;
	} catch ( err ) {
		return view.buildError( err );
	}
}

const submitIdleNode = select( '#cs-form-submitIdle' );
const submitLoadingNode = select( '#cs-form-submitLoading' );
const outputLoadingNode = select( '#cs-output-placeholder' );
const outputNode = select( '#cs-output' );

async function sendQuery( jsData ) {
	if ( !jsData || !jsData.apiQueryUrl ) {
		// Not a query submission
		return;
	}

	const repos = jsData.reposData;
	const queryState = {
		format: 'Default',
		regexp: null,
		getRegexp() {
			if ( !queryState.regexp ) {
				// Optimisation: Cache regex creation to re-use *many* times.
				// Correctness: Defer this until needed because when the input contains
				// invalid syntax, we want the detailed server error to be reported in the UI,
				// and not an early generic SyntaxError from this code.
				queryState.regexp = new RegExp(
					jsData.fields.query,
					jsData.fields.caseInsensitive ? 'ig' : 'g'
				);
			}
			return queryState.regexp;
		},
		time: {
			fetchStart: now(),
			fetchDuration: null,
			renderStart: null,
			renderDuration: null
		}
	};

	let apiData;
	try {
		apiData = await fetchResults( jsData.apiQueryUrl );
	} catch ( err ) {
		outputNode.append( view.buildError( err ) );
	}
	queryState.time.renderStart = now();
	queryState.time.fetchDuration = Math.round( queryState.time.renderStart - queryState.time.fetchStart );

	// Stop loading animation
	submitIdleNode.hidden = false;
	submitLoadingNode.hidden = outputLoadingNode.hidden = true;

	// Load more callback
	const loadFn = async ( repoId, sectionNode, completeFn ) => {
		const repoConf = repos[ repoId ];
		let result;
		try {
			const resp = await fetchResults( formatApiQueryUrl( jsData.apiQueryUrl, repoId, OFFSET_MORE ) );
			result = resp.Results && resp.Results[ repoId ];
			if ( !result ) {
				throw new Error( 'No additional matches found' );
			}
		} catch ( err ) {
			sectionNode.append( view.buildError( err ) );
			return;
		} finally {
			completeFn();
		}

		sectionNode.append(
			...result.Matches.map( ( match ) =>
				view.buildResultDefaultCard( match, repoConf, result.Revision, queryState.getRegexp() )
			)
		);
	};
	// Refresh callback
	const rerenderFn = () => {
		outputNode.innerHTML = '';
		outputNode.append( renderResponse( repos, apiData, queryState, rerenderFn, loadFn ) );
	};

	outputNode.append( renderResponse(
		repos,
		apiData,
		queryState,
		rerenderFn,
		loadFn
	) );
	queryState.time.renderDuration = Math.round( now() - queryState.time.renderStart );
	// cs-perf is absent on "No results found" response
	outputNode.querySelector( '.cs-perf' )?.setAttribute( 'data-time-render', queryState.time.renderDuration );
}

// Main init
{
	const jsData = window.CS_JSDATA;
	if ( jsData ) {
		sendQuery( jsData );

		const formNode = select( '#cs-form' );
		formNode.addEventListener( 'submit', function () {
			// Start loading animation right away, while the page is reloading
			submitIdleNode.hidden = true;
			submitLoadingNode.hidden = outputLoadingNode.hidden = false;
			// Hide results but don't empty the output element.
			// We keep results in-memory, to instantly restore from BFCache
			// when using native back button.
			outputNode.hidden = true;
			outputNode.dataset.hasresults = '1';
		} );

		const reposHiddenNode = select( '#cs-field-repos' );
		const reposSelectorNode = select( '#cs-field-reposelector' );
		const reposInputNode = reposSelectorNode.querySelector( 'input' );
		const reposLabelNode = reposSelectorNode.querySelector( 'label' );
		const reposDropdownNode = reposSelectorNode.querySelector( '.dropdown-menu' );
		const repoSelectState = {
			isOpen: false,
			selected: new Set(
				jsData.fields.repos.split( ',' ).map( ( val ) => val.trim() ).filter( Boolean )
			),
			open() {
				if ( !repoSelectState.isOpen ) {
					repoSelectState.isOpen = true;
					reposDropdownNode.classList.add( 'show' );
				}
			},
			close() {
				if ( repoSelectState.isOpen ) {
					repoSelectState.isOpen = false;
					reposDropdownNode.classList.remove( 'show' );
				}
			},
			sync() {
				// Update summary label
				reposLabelNode.textContent = repoSelectState.selected.size ?
					`Select repos (${repoSelectState.selected.size})` :
					'Select repos';
				// Persist back to hidden input field for form submittion
				reposHiddenNode.value = Array.from( repoSelectState.selected ).sort().join( ',' );
			},
			options: Object.keys( jsData.reposData ).sort()
		};
		const onRepoInput = () => {
			reposDropdownNode.replaceChildren(
				view.buildRepoSelector( reposInputNode.value, repoSelectState, jsData.repoIndexUrl )
			);
			repoSelectState.open();
		};
		const onRepoDropdownChange = ( e ) => {
			const checkbox = e.target;
			if ( checkbox.checked ) {
				repoSelectState.selected.add( checkbox.value );
			} else {
				repoSelectState.selected.delete( checkbox.value );
			}
			repoSelectState.sync();
		};
		reposInputNode.addEventListener( 'focus', onRepoInput );
		reposInputNode.addEventListener( 'input', onRepoInput );
		reposDropdownNode.addEventListener( 'change', onRepoDropdownChange );
		// Hide dropdown when pressing Escape, clicking/tabbing outside of it
		const onDocumentKey = ( e ) => {
			if ( repoSelectState.isOpen && e.code === 'Escape' ) {
				repoSelectState.close();
			}
		};
		const onDocumentTarget = ( e ) => {
			if ( repoSelectState.isOpen && !reposSelectorNode.contains( e.target ) ) {
				repoSelectState.close();
			}
		};
		document.addEventListener( 'keydown', onDocumentKey );
		document.addEventListener( 'click', onDocumentTarget );
		document.addEventListener( 'focusin', onDocumentTarget );

		window.addEventListener( 'pageshow', ( e ) => {
			if ( e.persisted && outputNode.dataset.hasresults ) {
				// Restored from BFCache
				submitIdleNode.hidden = false;
				submitLoadingNode.hidden = outputLoadingNode.hidden = true;
				outputNode.hidden = false;
			}
		} );
	}
}
