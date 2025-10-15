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
		'apps' => 'Mobile Apps',
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
	public const HOUND_BASE_PUBLIC = 'https://codesearch-backend.wmcloud.org';

	private const USER_AGENT = 'codesearch-frontend <https://gerrit.wikimedia.org/g/labs/codesearch>';
	private const META_CACHE_TTL = 3600;

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
			$this->debug( sprintf( 'APCu cache hit for %s', $key ) );
		} else {
			$this->debug( sprintf( 'APCu cache miss for %s', $key ) );
			$val = $callback();
			if ( $hasApcu ) {
				apcu_store( $key, $val, $ttl );
				$this->apcuStats['misses']++;
			}
		}
		return $val;
	}

	/**
	 * @see CodesearchDebug::debug
	 * @param string $msg
	 */
	public function debug( $msg ): void {
	}

	private function getHoundApi( string $backend, $houndBase = null ): string {
		$houndBase ??= rtrim( getenv( 'CODESEARCH_HOUND_BASE' ) ?: self::HOUND_BASE_PUBLIC, '/' );
		return "$houndBase/$backend/api";
	}

	public function getHealth(): array {
		$houndBase = rtrim( getenv( 'CODESEARCH_HOUND_BASE' ) ?: self::HOUND_BASE_PUBLIC, '/' );
		$result = $this->getHttp( "$houndBase/_health.json" );
		$health = json_decode( $result, true );
		if ( !is_array( $health ) ) {
			trigger_error( "Hound /_health.json returned " . substr( $result, 0, 1024 ) );
			throw new ApiUnavailable( "Hound /_health.json returned invalid data" );
		}
		return $health;
	}

	public function formatPublicSearchApi( string $backend, array $fields ): string {
		$params = [
			// List 'q' first, matching robots.txt
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
		return $this->getHoundApi( $backend, self::HOUND_BASE_PUBLIC ) . '/v1/search?' . http_build_query( $params );
	}

	public function getCachedConfig( string $backend ): array {
		return $this->getWithSetCallback(
			"codesearch-config-v1:$backend",
			self::META_CACHE_TTL,
			function () use ( $backend ) {
				$url = $this->getHoundApi( $backend ) . '/v1/repos';
				$val = json_decode( $this->getHttp( $url ), true );
				if ( !$val ) {
					throw new ApiUnavailable( 'Hound /v1/repos returned empty or invalid data' );
				}
				// Optimization: Strip out data not needed by client
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

	public function getCachedExcludes( string $backend ): array {
		return $this->getWithSetCallback(
			"codesearch-excludes-v1:$backend",
			self::META_CACHE_TTL,
			function () use ( $backend ) {
				$urls = [];
				$reposData = $this->getCachedConfig( $backend );
				foreach ( $reposData as $repo => $_ ) {
					$urls[$repo] = $this->getHoundApi( $backend ) . '/v1/excludes?' . http_build_query( [ 'repo' => $repo ] );
				}
				$results = $this->getHttpMulti( $urls );

				$val = [];
				foreach ( $results as $repo => $result ) {
					$files = json_decode( $result, true );
					if ( !is_array( $files ) ) {
						trigger_error( "Hound /v1/excludes for $repo returned " . substr( $result, 0, 1024 ) );
						throw new ApiUnavailable( "Hound /v1/excludes for $repo returned invalid data" );
					}
					$val[] = [
						'repo' => $repo,
						'excludesCount' => count( $files ),
						'files' => $files,
					];
				}
				return $val;
			}
		);
	}

	protected function getHttp( string $url, $timeout = 3 ): string {
		$curlOptions = [
			CURLOPT_TIMEOUT => $timeout,
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
		$this->debug( sprintf( 'getHttp timeout=%d %s', $timeout, $url ) );
		$curlRes = curl_exec( $curlHandle );
		if ( curl_errno( $curlHandle ) == CURLE_OPERATION_TIMEOUTED ) {
			throw new ApiUnavailable( "Hound request timed out after $timeout seconds" );
		}
		if ( $curlRes === false ) {
			throw new ApiUnavailable( 'Hound request failed: ' . curl_error( $curlHandle ) );
		}
		curl_close( $curlHandle );
		return $curlRes;
	}

	protected function getHttpMulti( array $urls, $throttled = false ): array {
		if ( !$throttled ) {
			$this->debug( sprintf( 'getHttpMulti chunking %d requests', count( $urls ) ) );

			$results = [];
			$t = null;
			foreach ( array_chunk( $urls, 99, true ) as $chunk ) {

				// Avoid HTTP 429 from WMCS dynamicproxy (ratelimit of 100/s)
				// Note that only the sleep is conditional, the chunking is not.
				// We don't want to send 1000+ requests at once, as they will not
				// complete within the timeout.
				if ( !getenv( 'CODESEARCH_HOUND_BASE' ) ) {
					// usleep in microseconds, hrtime in nanoseconds
					$remainingUs = !$t ? 0 : ceil( 1e6 - ( ( hrtime( true ) - $t ) / 1000 ) );
					if ( $remainingUs > 0 ) {
						$this->debug( sprintf( 'getHttpMulti sleeping %dms between chunks', $remainingUs / 1000 ) );
						usleep( $remainingUs );
					}
					$t = hrtime( true );
				}

				$results += $this->getHttpMulti( $chunk, true );
			}
			return $results;
		}

		$cmh = curl_multi_init();
		curl_multi_setopt( $cmh, CURLMOPT_MAXCONNECTS, 50 );
		curl_multi_setopt( $cmh, CURLMOPT_PIPELINING, CURLPIPE_MULTIPLEX );

		$infos = [];
		$curlOptions = [
			CURLOPT_TIMEOUT => 3,
			CURLOPT_MAXREDIRS => 2,
			CURLOPT_FOLLOWLOCATION => true,
			CURLOPT_USERAGENT => self::USER_AGENT,
			CURLOPT_HTTPHEADER => [],
			CURLOPT_RETURNTRANSFER => true,
			CURLOPT_HEADERFUNCTION => static function ( $ch, $header ) use ( &$infos ) {
				$len = strlen( $header );
				// HTTP/2 responds with only a number, no textual reason as well
				if ( preg_match( "/^HTTP\/(?:1\.[01]|2) (\d+)/", $header, $m ) ) {
					$infos[ (int)$ch ]['status'] = (int)$m[1];
				}
				return $len;
			},
			// Inspired by MultiHttpClient from MediaWiki 1.42
			CURLOPT_PIPEWAIT => 1,
		];

		$this->debug( sprintf( 'getHttpMulti with %d requests', count( $urls ) ) );
		foreach ( $urls as $urlKey => $url ) {
			$curlHandle = curl_init( $url );
			if ( !curl_setopt_array( $curlHandle, $curlOptions ) ) {
				throw new RuntimeException( 'Could not set curl options' );
			}
			$infos[(int)$curlHandle] = [
				'urlKey' => $urlKey,
				'handle' => $curlHandle,
				'result' => null,
				'status' => null,
			];
			curl_multi_add_handle( $cmh, $curlHandle );
		}

		// Execute multiple handles at once
		$active = null;
		do {
			$status = curl_multi_exec( $cmh, $active );
			if ( $active ) {
				curl_multi_select( $cmh );
			}
			// phpcs:ignore MediaWiki.ControlStructures.AssignmentInControlStructures
			while ( ( $info = curl_multi_info_read( $cmh ) ) !== false ) {
				/** @var $info false|array{msg:int,result:int,handle:object} */
				$infos[ (int)$info['handle'] ]['result'] = $info['result'];
			}
		} while ( $active > 0 && $status == CURLM_OK );

		'@phan-var array{urlKey:string,handle:object,result:?int,status:?int}[] $infos';

		$results = [];
		foreach ( $infos as $_ => $info ) {
			$urlKey = $info['urlKey'];
			if ( $info['result'] !== null && $info['result'] !== 0 ) {
				throw new ApiUnavailable( "Request {$urls[$urlKey]} failed " . curl_strerror( $info['result'] ) );
			}
			if ( $info['status'] >= 400 ) {
				throw new ApiUnavailable( "Request {$urls[$urlKey]} failed HTTP " . $info['status'] );
			}
			$result = curl_multi_getcontent( $info['handle'] );
			curl_multi_remove_handle( $cmh, $info['handle'] );
			curl_close( $info['handle'] );
			$results[$urlKey] = $result;
		}

		curl_multi_close( $cmh );
		return $results;
	}
}
