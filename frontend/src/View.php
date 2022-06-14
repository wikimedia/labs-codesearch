<?php
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
namespace Wikimedia\Codesearch;

use Mustache;
use Mustache_Engine;

class View {
	public function __construct(
		private string $template,
		private array $data
	) {
	}

	public function render(): string {
		if ( class_exists( Mustache::class ) ) {
			// Prefer native php-mustache (PECL) when available (e.g. Dockerfile build)
			$mustache = new Mustache();
		} else {
			// Fallback to composer bobthecow/mustache.php for local dev server
			$mustache = new Mustache_Engine( [
				'entity_flags' => ENT_QUOTES
			] );
		}

		$templateFile = dirname( __DIR__ ) . '/templates/' . $this->template . '.mustache';
		$templateContent = file_get_contents( $templateFile );

		return $mustache->render( $templateContent, $this->data );
	}
}
