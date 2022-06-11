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

use Mustache_Engine;
use Mustache_Loader_FilesystemLoader;

class View {
	public function __construct(
		private string $template,
		private array $data
	) {
	}

	public function render(): string {
		// TODO: Use native php-mustache when available (e.g. Dockerfile build)
		// instead of composer bobthecow/mustache.php (e.g. local dev server)
		$mustache = new Mustache_Engine( [
			'entity_flags' => ENT_QUOTES,
			'loader' => new Mustache_Loader_FilesystemLoader( dirname( __DIR__ ) . '/templates' ),
		] );

		return $mustache->render( $this->template, $this->data );
	}
}
