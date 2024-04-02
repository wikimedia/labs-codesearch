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

import { dom, fuzzyFilter } from './util.js';

const SUGGEST_LIMIT = 20;

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

function buildRepoSelector( inputText, repoSelectState, repoIndexUrl ) {
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

	optionElements.append(
		dom( 'div', { className: 'dropdown-item' }, [
			dom( 'a', { href: repoIndexUrl }, 'Complete repository list' )
		] )
	);

	return optionElements;
}

export {
	buildRepoSelector,
};
