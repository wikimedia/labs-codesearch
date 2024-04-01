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

use RuntimeException;

class Codesearch {
	public const BACKEND_DEFAULT = 'search';
	public const BACKENDS = [
		'search' => 'Everything',
		'core' => 'MediaWiki core',
		'extensions' => 'Extensions',
		'skins' => 'Skins',
		'things' => 'MW extensions & skins',
		'bundled' => 'MW tarball',
		'libraries' => 'MW libraries',
		'deployed' => 'MediaWiki & services at WMF',
		'operations' => 'Wikimedia SRE',
		'puppet' => 'Puppet',
		'ooui' => 'OOUI',
		'milkshake' => 'Milkshake',
		'pywikibot' => 'Pywikibot',
		'services' => 'Wikimedia Services',
		'devtools' => 'CI & Development',
		'analytics' => 'Data Engineering',
		'wmcs' => 'Wikimedia Cloud Services',
		'armchairgm' => 'ArmchairGM',
		'shouthow' => 'ShoutHow',
	];
	public const BACKENDS_HIDDEN = [
		'armchairgm' => true,
		'extensions' => true,
		'milkshake' => true,
		'ooui' => true,
		'services' => true,
		'shouthow' => true,
		'skins' => true,
	];
	public const URL_HEALTH = 'https://codesearch-backend.wmcloud.org/_health';
	private const URL_HOUND_BASE = 'https://codesearch-backend.wmcloud.org/';
	private const USER_AGENT = 'codesearch-frontend <https://gerrit.wikimedia.org/g/labs/codesearch>';
	private const REPOS_CACHE_TTL = 3600;

	private array $apcuStats = [
		'hits' => 0,
		'misses' => 0,
	];

	public function getBackendLabel( string $backend ): ?string {
		return self::BACKENDS[ $backend ] ?? null;
	}

	public function getApcuStats(): array {
		return $this->apcuStats + [ 'enabled' => function_exists( 'apcu_fetch' ) ];
	}

	protected function getWithSetCallback( string $key, int $ttl, $callback ) {
		$hasApcu = function_exists( 'apcu_fetch' );
		$val = $hasApcu ? apcu_fetch( $key ) : false;
		if ( $val !== false ) {
			$this->apcuStats['hits']++;
		} else {
			$val = $callback();
			if ( $hasApcu ) {
				apcu_store( $key, $val, $ttl );
				$this->apcuStats['misses']++;
			}
		}
		return $val;
	}

	private function getHoundApi( string $backend ): string {
		return self::URL_HOUND_BASE . "$backend/api";
	}

	public function formatApiQueryUrl( string $backend, array $fields ): string {
		$params = [
			'q' => $fields['query'],
			'i' => $fields['caseInsensitive'] ? 'fosho' : null,
			'files' => $fields['filePath'],
			'excludeFiles' => $fields['excludeFiles'],
			'repos' => $fields['repos'] ?: '*',
			'stats' => 'fosho',
			// Enable rng ("offset:limit") to limit results to "page 1".
			// "Load more" is handled in codesearch.js.
			'rng' => ':20',
		];
		return $this->getHoundApi( $backend ) . '/v1/search?' . http_build_query( $params );
	}

	public function getCachedConfig( string $backend ): array {
		return $this->getWithSetCallback(
			"codesearch-config-v1:$backend",
			self::REPOS_CACHE_TTL,
			function () use ( $backend ) {
				$url = $this->getHoundApi( $backend ) . '/v1/repos';
				$val = json_decode( $this->getHttp( $url ), true );
				if ( !$val ) {
					throw new ApiUnavailable( 'Hound /v1/repos returned empty or invalid data' );
				}
				// Strip out data not needed by client
				foreach ( $val as $repoId => &$repoConf ) {
					$repoConf = [
						'url' => $repoConf['url'],
						'url-pattern' => $repoConf['url-pattern'],
					];
				}
				return $val;
			}
		);
	}

	protected function getHttp( string $url ): string {
		$curlOptions = [
			// timeout in seconds
			CURLOPT_TIMEOUT => 3,
			CURLOPT_MAXREDIRS => 2,
			CURLOPT_FOLLOWLOCATION => true,
			CURLOPT_USERAGENT => self::USER_AGENT,
			CURLOPT_HTTPHEADER => [],
			CURLOPT_RETURNTRANSFER => true,
		];
		$curlHandle = curl_init( $url );
		if ( !curl_setopt_array( $curlHandle, $curlOptions ) ) {
			throw new RuntimeException( 'Could not set curl options' );
		}
		$curlRes = curl_exec( $curlHandle );
		if ( curl_errno( $curlHandle ) == CURLE_OPERATION_TIMEOUTED ) {
			throw new ApiUnavailable( 'Internal curl request timed out' );
		}
		if ( $curlRes === false ) {
			throw new ApiUnavailable( 'Internal curl request failed: ' . curl_error( $curlHandle ) );
		}
		curl_close( $curlHandle );
		return $curlRes;
	}

}
