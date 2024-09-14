<?php
/**
 * Copyright (C) 2024 Timo Tijhof
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

class CodesearchDebug extends Codesearch {
	public function debug( $msg ): void {
		static $i = 0;
		$i++;
		$n = str_pad( "$i", 3, '0', STR_PAD_LEFT );
		$mem = round( memory_get_usage() / 1024 / 1024 )
			. 'M/'
			. round( memory_get_peak_usage() / 1024 / 1024 )
			. 'M';

		// For local development, unconditionally output debug logs to 'composer serve',
		// to ease debugging of slow requests. When using Docker (production, or locally),
		// we limit this via index.php to only when setting 'debug=1'
		error_log( "codesearch-frontend [DEBUG $n mem=$mem] $msg" );
	}
}
