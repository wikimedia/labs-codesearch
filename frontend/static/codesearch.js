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

import { select } from './util.js';
import * as view from './view.js';

const outputNode = select( '#cs-output' );

// "Load more" button
//
// Optimisation: Server-side Mustache must wrap each repo's results in a <section>.
//
// If we didn't have the <section> wrapper, and when using the "Load more results"
// feature, we just inserted the extra "card" elements as siblings in-between
// other headings and cards as children of "cs-results", the browser would have
// to re-evaluate basically the entire page. With this wrapper, the browser only
// has to re-render this section, and the rest simply moves down.
// Example: Search for `"authors"` on the "Everywhere" backend, and then
// click "Load more". This makes the difference (in Firefox) between DOM append()
// being instant (<50ms) vs taking several whole seconds.
if ( window.CS_CLIENT && outputNode ) {
	outputNode.addEventListener( 'click', async function ( e ) {
		if ( !e.target.matches( 'button.cs-loadmore' ) ) {
			return;
		}
		const button = e.target;
		button.disabled = true;
		button.textContent = 'Fetching more matches...';
		button.insertAdjacentHTML(
			'afterbegin',
			'<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>&nbsp;'
		);
		const resp = await fetch( button.dataset.moresrc );
		const html = await resp.text();
		button.insertAdjacentHTML( 'beforebegin', html );
		button.remove();
	} );
}

// Repo selector
const jsData = window.CS_JSDATA;
if ( window.CS_CLIENT && jsData ) {
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
				`Select repos (${ repoSelectState.selected.size })` :
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
}

// Respond to navigations from form submit or backward- navigations
{
	const submitIdleNode = select( '#cs-form-submitIdle' );
	const submitLoadingNode = select( '#cs-form-submitLoading' );
	const outputPlaceholderNode = select( '#cs-output-placeholder' );

	const onSubmit = function () {
		// Start loading animation right away, while the page is reloading
		submitIdleNode.hidden = true;
		submitLoadingNode.hidden = false;
		outputPlaceholderNode.hidden = false;

		// Hide results but don't empty the output element.
		// We keep results in-memory, to instantly restore from BFCache
		// when using native back button.
		if ( outputNode ) {
			outputNode.hidden = true;
			outputNode.dataset.hasresults = '1';
		}
	};

	const formNode = select( '#cs-form' );
	formNode.addEventListener( 'submit', onSubmit );

	const backendNav = select( '.nav-pills' );
	backendNav.addEventListener( 'click', ( e ) => {
		// Switching backends with non-empty query is functionally a submision
		if ( e.target.matches( 'a[href]' ) && ( new URLSearchParams( e.target.search ) ).get( 'q' ) ) {
			onSubmit();
		}
	} );
	window.addEventListener( 'pageshow', ( e ) => {
		if ( e.persisted && outputNode && outputNode.dataset.hasresults ) {
			// Restored from BFCache
			submitIdleNode.hidden = false;
			submitLoadingNode.hidden = true;
			outputPlaceholderNode.hidden = true;
			outputNode.hidden = false;
		}
	} );
}
