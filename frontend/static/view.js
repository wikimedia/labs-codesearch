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

import { dom, flattenMatchesToLines, fuzzyFilter } from './util.js';

const SUGGEST_LIMIT = 20;

/**
 * @param {Object} repoConf
 * @param {string} rev
 * @param {string} path
 * @param {number|undefined} lineno
 * @return {string}
 */
function formatUrl( repoConf, rev, path, lineno ) {
	const anchor = ( lineno !== undefined ?
		repoConf[ 'url-pattern' ].anchor.replace( '{line}', lineno ) :
		''
	);

	return repoConf[ 'url-pattern' ][ 'base-url' ]
		.replace( '{url}', repoConf.url )
		.replace( '{rev}', rev )
		.replace( '{path}', path )
		.replace( '{anchor}', anchor );
}

function highlightLine( text, regexp ) {
	const children = [];
	while ( true ) {
		regexp.lastIndex = 0;
		const m = regexp.exec( text );
		if ( !m ) {
			children.push( text );
			break;
		}

		children.push(
			text.slice( 0, regexp.lastIndex - m[ 0 ].length ),
			dom( 'em', undefined, [ m[ 0 ] ] )
		);
		text = text.slice( regexp.lastIndex );
	}
	return children;
}

/**
 * @param {Error} err
 * @return {HTMLElement}
 */
function buildError( err ) {
	// Log for visibility and ease of jumping into debugging
	// eslint-disable-next-line no-console
	console.error( err );

	return dom( 'div', {
		className: 'alert alert-warning',
		role: 'alert'
	}, [ err.toString() ] );
}

function buildFormatNav( repos, apiData, state, rerenderFn ) {
	const stats = apiData.Stats;

	return dom( 'div', { className: 'row mb-3 mb-lg-0 ' }, [
		dom( 'div', { className: 'form-text col-auto' }, [ 'Result format:' ] ),
		dom( 'div', { className: 'btn-group col-auto', role: 'group', 'aria-label': 'Result format' },
			[ 'Default', 'Phabricator' ].flatMap( ( format ) => [
				dom( 'input', { type: 'radio', className: 'btn-check', id: `cs-result-${format}`,
					name: 'format',
					value: format,
					autocomplete: 'off',
					oninput: () => {
						state.format = format;
						rerenderFn();
					},
					checked: state.format === format
				} ),
				dom( 'label', { className: 'btn btn-outline-secondary', for: `cs-result-${format}` },
					[ format ]
				)
			] )
		),
		dom( 'div', { className: 'form-text col-auto flex-grow-1 text-end cs-perf', 'data-time-backend': stats.Duration, 'data-files': stats.FilesOpened } )
	] );
}

function buildResultsPhabricator( repos, resultsOriginal ) {
	return dom( 'textarea',
		{
			className: 'col-12 mt-3 font-monospace cs-phabresult',
			readonly: true,
			onclick: ( e ) => {
				if ( e.currentTarget.focus ) {
					e.currentTarget.select();
				}
			}
		},
		Object.entries( resultsOriginal ).flatMap( ( [ repoId, result ] ) => {
			return [
				`[ ] ${repoId} (${result.FilesWithMatch} files)\n`,
				...result.Matches.map( ( match ) => {
					const repoConf = repos[ repoId ];
					const url = formatUrl( repoConf, result.Revision, match.Filename, undefined );
					return `** [[${url}|${match.Filename}]] (${match.Matches.length} matches)\n`;
				} )
			];
		} )
	);
}

function buildResultDefaultCard( match, repoConf, resultRevision, regexp ) {
	return dom( 'details', { open: true, className: 'card mb-3' }, [
		dom( 'summary', { className: 'card-header' }, [
			dom( 'a', {
				className: 'link-secondary',
				href: formatUrl( repoConf, resultRevision, match.Filename, undefined ),
				target: '_blank'
			}, [ match.Filename ] )
		] ),
		dom( 'div', { className: 'card-body cs-result' },
			flattenMatchesToLines( match.Matches )
				.map( ( line ) => dom( 'div', {
					className: line.isMatchBoundary ? 'cs-line cs-line-boundary' : 'cs-line'
				}, [
					dom( 'a', {
						className: 'link-secondary cs-line-no',
						href: formatUrl( repoConf, resultRevision, match.Filename, line.lineno ),
						target: '_blank'
					}, [ String( line.lineno ) ] ),
					dom( 'code', { className: 'cs-line-code' },
						line.isMatch ? highlightLine( line.text, regexp ) : [ line.text ]
					)
				] ) )
		)
	] );
}

function buildResultsDefault( repos, resultsOriginal, state, loadFn ) {
	// Example for `repos`
	// {   "MediaWiki core": {
	//         "url": "..",
	//         "url-pattern": {
	//             "base-url": "https://gerrit.wikimedia.org/g/mediawiki/core/+/{rev}/{path}{anchor}",
	//             "anchor": "#{line}"
	//         }
	//     }
	// }
	// Example for `resultsOriginal`
	// {   "MyRepoName": {
	//           "Matches": [{
	//               "Filename": "example/file.txt",
	//               "Matches": [{
	//                   "Line": "A line with a matched word",
	//                   "LineNumber": 43,
	//                   "Before": ["Something", "Before"],
	//                   "After": ["And", "After"],
	//               }, ..]
	//           }, ..],
	//           "FilesWithMatch": 3,
	//           "Revision": "0ac66edf0a91d8687ce0e54d3af2944b3028ab1d"
	//     }
	// }
	const results = Object.entries( resultsOriginal );

	// Backward sort by FilesWithMatch, then forward sort by repoId
	results.sort( ( [ aRepo, aResult ], [ bRepo, bResult ] ) => {
		if ( aResult.FilesWithMatch === bResult.FilesWithMatch ) {
			return aRepo > bRepo ? 1 : -1;
		} else {
			return bResult.FilesWithMatch - aResult.FilesWithMatch;
		}
	} );

	return dom( 'div', { className: 'row' }, [
		dom( 'div', { className: 'col-lg-7 col-xl-8 order-2 order-lg-1 mt-3 cs-results' },
			results.map( ( [ repoId, result ] ) => {
				const hasMore = result.FilesWithMatch > result.Matches.length;
				const repoConf = repos[ repoId ];
				if ( !repoConf ) {
					throw new Error( 'Missing repo metadata for ' + repoId );
				}

				// Optimisation: Wrap the results from the same repo into an element.
				//
				// When using the "Load more results" feature, if we don't have this wrapper,
				// and we instead insert extra cards in-between all other headings/cards into
				// the singular cs-results element, the browser has to re-evaluate basically
				// the entire page. With this wrapper, the browser only has to re-render this
				// section, and the rest simply moves down. For a search like `"authors"` to
				// the "Everywhere" backend, and then clicking "Load more", this makes the
				// difference in Firefox between append() being instant (<50ms) vs taking
				// several seconds.
				return dom( 'section', undefined, [
					dom( 'h2', { id: repoId }, [ repoId ] ),
					...result.Matches.map( ( match ) =>
						buildResultDefaultCard( match, repoConf, result.Revision, state.getRegexp() )
					),
					hasMore ?
						dom( 'button', {
							className: 'btn btn-secondary',
							type: 'button',
							onclick: ( e ) => {
								const button = e.currentTarget;
								const section = button.parentNode;

								button.disabled = true;
								button.textContent = `Loading matches in ${repoId}....`;
								button.insertAdjacentHTML(
									'afterbegin',
									'<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>&nbsp;'
								);

								loadFn( repoId, section, () => {
									button.remove();
								} );
							}
						}, [ `Load all ${result.FilesWithMatch} matches in ${repoId}` ] ) :
						''
				] );
			} )
		),
		dom( 'div', { className: 'col-lg-5 col-xl-4 order-1 order-lg-2 cs-reposlist' }, [
			dom( 'p', { className: 'h5' }, 'Matched repositories' ),
			dom( 'div', { className: 'list-group' },
				results.map( ( [ repoId, result ] ) =>
					dom( 'a', { className: 'list-group-item list-group-item-action d-flex justify-content-between align-items-center', href: '#' + repoId }, [
						repoId + ' ',
						dom( 'span', { className: 'badge bg-secondary rounded-pill' }, String( result.FilesWithMatch ) )
					] )
				)
			)
		] )
	] );
}

function buildRepoOption( repoId, checked, i ) {
	return dom( 'div', { className: 'dropdown-item', role: 'option', 'aria-selected': 'false' }, [
		dom( 'span', { className: 'form-check' }, [
			dom( 'input', {
				type: 'checkbox',
				checked: checked,
				value: repoId,
				className: 'form-check-input',
				id: 'cs-field-repo' + i,
			} ),
			dom( 'label', { className: 'form-check-label d-block', for: 'cs-field-repo' + i }, [
				repoId
			] )
		] )
	] );
}

function buildRepoSelector( inputText, repoSelectState ) {
	const suggestions = fuzzyFilter( inputText, repoSelectState.options, SUGGEST_LIMIT );

	let i = 1;
	const optionElements = document.createDocumentFragment();
	repoSelectState.selected.forEach( ( repoId ) => {
		optionElements.append( buildRepoOption( repoId, true, i++ ) );
	} );

	for ( const obj of suggestions ) {
		if ( !repoSelectState.selected.has( obj.target ) ) {
			optionElements.append( buildRepoOption( obj.target, false, i++ ) );
		}
	}
	return optionElements;
}

export {
	highlightLine,
	formatUrl,
	buildError,
	buildFormatNav,
	buildResultsPhabricator,
	buildResultDefaultCard,
	buildResultsDefault,
	buildRepoSelector,
};
