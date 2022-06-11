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

class Response {
	public function __construct(
		public int $statusCode = 200,
		public array $headers = [],
		public ?View $view = null
	) {
	}

	public function send(): void {
		http_response_code( $this->statusCode );

		foreach ( $this->headers as $header ) {
			header( $header );
		}

		if ( $this->view ) {
			print $this->view->render();
		}
	}
}
