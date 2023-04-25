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

/* global fuzzysort */

function select( selector ) {
	return document.querySelector( selector );
}

/**
 * @param {string} tagName
 * @param {Object|undefined} props
 * @param {Array<string|HTMLElement>|undefined} [children]
 * @return {HTMLElement}
 */
function dom( tagName, props, children ) {
	const element = document.createElement( tagName );
	if ( props ) {
		for ( const key in props ) {
			if ( key in element ) {
				// DOM IDL properties
				element[ key ] = props[ key ];
			} else {
				// E.g. aria/role attributes
				element.setAttribute( key, props[ key ] );
			}
		}
	}
	if ( children ) {
		element.append( ...children );
	}
	return element;
}

function isEmpty( obj ) {
	// eslint-disable-next-line no-unreachable-loop
	for ( const key in obj ) {
		return false;
	}
	return true;
}

/**
 * Escape string for safe inclusion in a regular expression.
 *
 * The following characters are escaped:
 *
 *     \ { } ( ) | . ? * + - ^ $ [ ]
 *
 * @param {string} str String to escape
 * @return {string} Escaped string
 */
function escapeRegExp( str ) {
	// eslint-disable-next-line no-useless-escape
	return str.replace( /([\\{}()|.?*+\-^$\[\]])/g, '\\$1' );
}

/**
 * Flatten and combine each Hound match into a single de-duplicated list of lines.
 *
 * @param {Array} matches
 * @return {Array}
 */
function flattenMatchesToLines( matches ) {
	let lines = new Map();
	// Optimisation: Gather all information in a single pass
	// without intermediary arrays, merges, fn calls, etc.
	for ( const match of matches ) {
		const matchedLineno = match.LineNumber;

		// Set the matched line unconditionally
		lines.set( matchedLineno, {
			lineno: matchedLineno,
			text: match.Line,
			isMatch: true,
			isMatchBoundary: false
		} );

		// Improve upon the default Hound UI by merging match blocks together.
		// This way we avoid displaying the same line multiple times, and avoids
		// needless separator lines when one match's last context line neatly
		// into the next match's first context line.

		// Record new before/after context lines only if not already seen,
		// including and especially if the existing entry for this line is a
		// matching line (which we must not overwrite with a context line).
		const totalBefore = match.Before.length;
		for ( let i = 0; i < match.Before.length; i++ ) {
			const lineno = matchedLineno - totalBefore + i;
			if ( !lines.has( lineno ) ) {
				lines.set( lineno, {
					lineno,
					text: match.Before[ i ],
					isMatch: false,
					isMatchBoundary: false
				} );
			}
		}
		for ( let i = 0; i < match.After.length; i++ ) {
			const lineno = matchedLineno + 1 + i;
			if ( !lines.has( lineno ) ) {
				lines.set( lineno, {
					lineno,
					text: match.After[ i ],
					isMatch: false,
					isMatchBoundary: false
				} );
			}
		}
	}

	lines = Array.from( lines.values() );
	lines.sort( ( a, b ) => a.lineno - b.lineno );
	lines.reduce( ( prev, line ) => {
		line.isMatchBoundary = prev.lineno + 1 !== line.lineno;
		return line;
	} );
	return lines;
}

function fuzzyFilter( inputText, options, limit ) {
	if ( inputText === '' ) {
		// Improve discovery of the feature by displaying results right away
		// on-focus even if input is empty. This also speeds up UX for cases
		// where only a handful of options exist.
		return options.slice( 0, limit ).map( ( target ) => {
			// Fake empty results. https://github.com/farzher/fuzzysort/issues/41
			return { target };
		} );
	} else {
		return fuzzysort.go( inputText, options, {
			limit: limit,
			allowTypo: true
		} );
	}
}

export {
	select,
	dom,
	isEmpty,
	escapeRegExp,
	flattenMatchesToLines,
	fuzzyFilter,
};

export const now = typeof performance !== 'undefined' && performance.now ?
	performance.now.bind( performance ) :
	Date.now;

// Polyfills

function replaceChildren( ...nodes ) {
	while ( this.lastChild ) {
		this.removeChild( this.lastChild );
	}
	this.append( ...nodes );
}

if ( !Element.prototype.replaceChildren ) {
	Element.prototype.replaceChildren = replaceChildren;
	DocumentFragment.prototype.replaceChildren = replaceChildren;
}
