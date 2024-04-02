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
	fuzzyFilter,
};

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
