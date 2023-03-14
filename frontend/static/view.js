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

import { html, flattenMatchesToLines, fuzzyFilter } from './util.js';

const SUGGEST_LIMIT = 50;

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
		const matchedText = m[ 0 ];

		children.push(
			text.slice( 0, regexp.lastIndex - matchedText.length ),
			html`<em>${matchedText}</em>`
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

	return html`<div
		className="alert alert-warning"
		role=alert
	>${err.toString()}</div>`;
}

function buildFormatNav( repos, apiData, state ) {
	const stats = apiData.Stats;
	const formats = [ 'Default', 'Phabricator' ];

	return html`<div className="row mb-3 mb-lg-0">
		<div className="form-text col-auto">Result format:</div>
		<div className="btn-group col-auto" role=group aria-label="Result format">
			${formats.map( ( format ) => html`
				<input type="radio" className="btn-check cs-field-format"
					id=cs-result-${format}
					name=${format}
					value=${format}
					autocomplete=off
					checked=${state.format === format}
				/>
				<label className="btn btn-outline-secondary" for="cs-result-${format}">
					${format}
				</label>` )}
		</div>
		<div className="form-text col-auto flex-grow-1 text-end cs-perf" data-time-backend=${stats.Duration} data-files=${stats.FilesOpened}></div>
	</div>`;
}

function buildResultsPhabricator( repos, resultsOriginal ) {
	let text = '';
	for ( const repoId in resultsOriginal ) {
		const result = resultsOriginal[ repoId ];
		text += `[ ] ${repoId} (${result.FilesWithMatch} files)\n`;
		for ( const match of result.Matches ) {
			const repoConf = repos[ repoId ];
			const url = formatUrl( repoConf, result.Revision, match.Filename, undefined );
			text += `** [[${url}|${match.Filename}]] (${match.Matches.length} matches)\n`;
		}
	}
	function onClick( e ) {
		if ( e.currentTarget.focus ) {
			e.currentTarget.select();
		}
	}
	return html`<textarea
		className="col-12 mt-3 font-monospace cs-phabresult"
		readonly=${true}
		onclick=${onClick}
	>
		${text}
	</textarea>`;
}

function buildResultDefaultCard( match, repoConf, result, state ) {
	return html`<div className="card mb-3">
		<div className="card-header">
			<a
				className="link-secondary"
				href=${formatUrl( repoConf, result.Revision, match.Filename, undefined )}
				target="_blank"
			>${match.Filename}</a>
		</div>
		<div className="card-body cs-result">
			${flattenMatchesToLines( match.Matches ).map( ( line ) => html`
				<div className=${line.isMatchBoundary ? 'cs-line cs-line-boundary' : 'cs-line'}>
					<a
						className="link-secondary cs-line-no"
						href=${formatUrl( repoConf, result.Revision, match.Filename, line.lineno )}
						target="_blank"
					>${String( line.lineno )}</a>
					<code className="cs-line-code">
						${line.isMatch ? highlightLine( line.text, state.regexp ) : line.text}
					</code>
				</div>` )}
		</div>
	</div>`;
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
	const results = [];
	for ( const repoId in resultsOriginal ) {
		const result = resultsOriginal[ repoId ];
		const hasMore = result.FilesWithMatch > result.Matches.length;
		const repoConf = repos[ repoId ];
		if ( !repoConf ) {
			throw new Error( 'Missing repo metadata for ' + repoId );
		}
		results.push( { repoId, result, hasMore, repoConf } );
	}

	// Backward sort by FilesWithMatch, then forward sort by repoId
	results.sort( ( a, b ) => {
		if ( a.result.FilesWithMatch === b.result.FilesWithMatch ) {
			return a.repoId > b.repoId ? 1 : -1;
		} else {
			return b.result.FilesWithMatch - a.result.FilesWithMatch;
		}
	} );

	function onButtonClick( button, repoId ) {
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

	// Optimisation: Wrap the results from the same repo into a <section> element.
	//
	// When using the "Load more results" feature, if we don't have this wrapper,
	// and we instead insert extra cards in-between all other headings/cards into
	// the singular cs-results element, the browser has to re-evaluate basically
	// the entire page. With this wrapper, the browser only has to re-render this
	// section, and the rest simply moves down. For a search like `"authors"` to
	// the "Everywhere" backend, and then clicking "Load more", this makes the
	// difference in Firefox between append() being instant (<50ms) vs taking
	// several seconds.
	return html`<div className="row">
		<div className="col-lg-7 col-xl-8 order-2 order-lg-1 mt-3 cs-results">
			${results.map( ( { repoId, result, hasMore, repoConf } ) => html`<section>
					<h2 id="${repoId}">${repoId}</h2>
					${result.Matches.map( ( match ) => buildResultDefaultCard( match, repoConf, result, state ) )}
					${hasMore ? html`<button
						className="btn btn-secondary"
						type="button",
						onclick=${( e ) => onButtonClick( e.currentTarget, repoId )}
						>Load all ${result.FilesWithMatch} matches in ${repoId}</button>` : ''}
				</section>` )}
		</div>
		<div className="col-lg-5 col-xl-4 order-1 order-lg-2 cs-reposlist">
			<p className="h5">Matched repositories</p>
			<div className="list-group">
				${results.map( ( { repoId, result } ) => html`
					<a
						className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
						href="#${repoId}"
					>
						${repoId} <span className="badge bg-secondary rounded-pill">${String( result.FilesWithMatch )}</span>
					</a>` )}
			</div>
		</div>
	</div>`;
}

function buildRepoOption( repoId, checked, i ) {
	return html`<div className="dropdown-item" role="option" aria-selected="false">
		<span className="form-check">
			<input
				type="checkbox"
				checked="${checked}"
				value="${repoId}"
				className="form-check-input"
				id="cs-field-repo${i}"
			/>
			<label for="cs-field-repo${i}" className="form-check-label d-block">${repoId}</label>
		</span>
	</div>`;
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
	if ( suggestions.length === SUGGEST_LIMIT ) {
		optionElements.append( html`<div className="dropdown-item cs-field-reposelector-foot">Limited to ${SUGGEST_LIMIT} suggestions</div>` );
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
