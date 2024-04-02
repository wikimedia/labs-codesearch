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

use UnexpectedValueException;

class Model {
	private const ACTIONS = [
		'search',
		'repos',
		'excludes',
		'more',
	];
	private string $action = '';
	private string $backend = '';
	private string $query = '';
	private bool $caseInsensitive = false;
	private string $filePath = '';
	private string $excludeFiles = '';
	private string $repos = '';

	public function __construct(
		private Codesearch $search
	) {
	}

	public function setURL( string $url ): self {
		$dir = basename( parse_url( $url, PHP_URL_PATH ) );
		return $this->setBackend( $dir );
	}

	public function setGetParams( array $get ): self {
		$this->setAction( $get['action'] ?? 'search' );
		$this->setSearchQuery( $get['q'] ?? '' );
		$this->setCaseInsensitive( ( $get['i'] ?? '' ) === 'fosho' );
		$this->setFilePath( $get['files'] ?? '' );
		$this->setExcludeFilePath( $get['excludeFiles'] ?? '' );
		$this->setRepos( $get['repos'] ?? '' );

		return $this;
	}

	public function setBackend( string $backend ): self {
		$this->backend = $backend;
		return $this;
	}

	public function setAction( string $action ): self {
		$this->action = $action;
		return $this;
	}

	public function setSearchQuery( string $query ): self {
		$this->query = trim( $query );
		return $this;
	}

	public function setCaseInsensitive( bool $caseInsensitive ): self {
		$this->caseInsensitive = $caseInsensitive;
		return $this;
	}

	public function setFilePath( string $filePath ): self {
		$this->filePath = $filePath;
		return $this;
	}

	public function setExcludeFilePath( string $excludeFiles ): self {
		$this->excludeFiles = $excludeFiles;
		return $this;
	}

	public function setRepos( string $repos ): self {
		$this->repos = trim( $repos );
		return $this;
	}

	/**
	 * Clean (but Hound-compatible) URL without 'backend' or 'repos'
	 *
	 * This is used when switching between backends, and when
	 * fetching SEARCH_OFFSET_MORE.
	 *
	 * @return array
	 */
	private function getCanonicalFrontendQuery(): array {
		return [
			'q' => $this->query !== '' ? $this->query : null,
			'i' => $this->caseInsensitive ? 'fosho' : null,
			'files' => $this->filePath !== '' ? $this->filePath : null,
			'excludeFiles' => $this->excludeFiles !== '' ? $this->excludeFiles : null,
		];
	}

	public function execute(): Response {
		$response = new Response();

		// Avoid dangling "?" by itself
		$canonicalFrontendQueryString = http_build_query( $this->getCanonicalFrontendQuery() );
		$canonicalFrontendQueryString = $canonicalFrontendQueryString
			? '?' . $canonicalFrontendQueryString
			: '';

		if ( $this->backend === '' ) {
			// Redirect to default backend
			$response->statusCode = 301;
			$response->headers[] =
				'Location: /' . Codesearch::BACKEND_DEFAULT . "/$canonicalFrontendQueryString";
			return $response;
		}

		$backends = [];
		foreach ( Codesearch::BACKENDS as $id => $label ) {
			if ( isset( Codesearch::BACKENDS_HIDDEN[$id] ) ) {
				continue;
			}
			$backends[] = [
				'href' => "/$id/$canonicalFrontendQueryString",
				'label' => $label,
				'active' => $id === $this->backend,
			];
		}

		$label = $this->search->getBackendLabel( $this->backend );
		if ( $label === null ) {
			$response->statusCode = 404;
			$error = "Unknown search backend \"{$this->backend}\".";
			$response->view = new View( 'error', [
				'doctitle' => 'Not found',
				'error' => $error,
				'backends' => $backends,
			] );
			return $response;
		}

		if ( !in_array( $this->action, self::ACTIONS ) ) {
			$response->statusCode = 404;
			$error = 'Unknown action.';
			$response->view = new View( 'error', [
				'doctitle' => 'Not found',
				'error' => $error,
				'backends' => $backends,
			] );
			return $response;
		}

		try {
			$reposData = $this->search->getCachedConfig( $this->backend );
		} catch ( ApiUnavailable $e ) {
			$response->statusCode = 501;
			$response->view = new View( 'health', [
				'doctitle' => 'Index unavailable',
				'backends' => $backends,
				'healthUrl' => Codesearch::URL_HEALTH,
			] );
			return $response;
		}

		if ( $this->action === 'repos' ) {
			$reposList = [];
			foreach ( $reposData as $label => $repo ) {
				$reposList[] = [ 'label' => $label, 'url' => $repo['url'] ];
			}
			$response->view = new View( 'repos', [
				'backends' => $backends,
				'reposList' => $reposList,
			] );
			return $response;
		}

		if ( $this->action === 'excludes' ) {
			$repoExcludes = $this->search->getCachedExcludes( $this->backend );
			$response->view = new View( 'excludes', [
				'backends' => $backends,
				'repoExcludes' => $repoExcludes,
			] );
			return $response;
		}

		$selectedRepos = explode( ',', $this->repos );
		$selectedRepos = array_intersect( $selectedRepos, array_keys( $reposData ) );
		$repos = implode( ',', $selectedRepos );

		$fields = [
			'query' => $this->query,
			'caseInsensitive' => $this->caseInsensitive,
			'filePath' => $this->filePath,
			'excludeFiles' => $this->excludeFiles,
			'repos' => $repos,
		];

		if ( $this->action === 'more' ) {
			if ( count( $selectedRepos ) !== 1 ) {
				$response->statusCode = 400;
				$error = 'Pagination operates on exactly one repo.';
				$response->view = new View( 'error', [
					'doctitle' => 'Bad request',
					'error' => $error,
					'backends' => $backends,
				] );
				return $response;
			}
			$searchResp = $this->processSearchResponse( $reposData,
				$this->search->fetchSearchResults(
					$this->backend,
					$fields,
					$this->search::SEARCH_OFFSET_MORE
				)
			);
			$response->view = new View( 'more', [
				'searchResp' => $searchResp,
			] );
			return $response;
		}

		$searchResp = ( $this->query !== '' )
			? $this->processSearchResponse( $reposData,
				$this->search->fetchSearchResults( $this->backend, $fields )
			)
			: null;

		$jsData = [
			// '_searchResp' => $searchResp, // DEBUG
			'reposData' => $reposData,
			'repoIndexUrl' => './?action=repos',
			'fields' => $fields,
			'debug' => [
				'apcuStats' => $this->search->getApcuStats(),
			],
		];
		$jsDataRawHtml = json_encode(
			$jsData,
			JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE
		);

		$response->view = new View( 'index', [
			'isSubmit' => (bool)$searchResp,
			'doctitle' => $searchResp ? $this->query : null,
			'backendLabel' => $label,
			'backends' => $backends,
			'fields' => $fields,
			'selectedRepoCount' => strval( count( $selectedRepos ) ?: '' ),
			'searchResp' => $searchResp,
			'jsDataRawHtml' => $jsDataRawHtml,
		] );
		return $response;
	}

	/**
	 * @param array $repoConf
	 * @param string $rev
	 * @param string $path
	 * @param int|null $lineno
	 * @return string
	 */
	private function formatUrl( $repoConf, $rev, $path, $lineno ) {
		$anchor = ( $lineno !== null
			? strtr( $repoConf[ 'url-pattern' ]['anchor'], [ '{line}' => $lineno ] )
			: ''
		);

		return strtr( $repoConf[ 'url-pattern' ][ 'base-url' ], [
			'{url}' => $repoConf['url'],
			'{rev}' => $rev,
			'{path}' => $path,
			'{anchor}' => $anchor,
		] );
	}

	/**
	 * Flatten and combine each Hound match into a single de-duplicated list of lines.
	 *
	 * @param array $matches
	 * @param array $repoConf For formatUrl()
	 * @param string $rev For formatUrl()
	 * @param string $path For formatUrl()
	 * @return array
	 */
	private function flattenMatchesToLines( $matches, $repoConf, $rev, $path ) {
		$lines = [];
		// Optimisation: Gather all information in a single pass
		// without intermediary arrays, merges, fn calls, etc.
		foreach ( $matches as $match ) {
			$matchedLineno = $match['LineNumber'];

			// Set the matched line unconditionally
			$lines[$matchedLineno] = [
				'lineno' => $matchedLineno,
				// Optimisation: It's worth calling formatUrl() directly with all args
				// instead of passing an indirect callables, trade-off is passing
				// down each arg a bit deeper.
				'href' => $this->formatUrl( $repoConf, $rev, $path, $matchedLineno ),
				'html' => $this->makeHighlightedHtml( $match['Line'] ),
				'isMatch' => true,
				'isMatchBoundary' => false,
			];

			// Improve upon the default Hound UI by merging match blocks together.
			// This way we avoid displaying the same line multiple times, and avoids
			// needless separator lines when one match's last context line neatly
			// into the next match's first context line.

			// Record new before/after context lines only if not already seen,
			// including and especially if the existing entry for this line is a
			// matching line (which we must not overwrite with a context line).
			$totalBefore = count( $match['Before'] );
			foreach ( $match['Before'] as $i => $text ) {
				$lineno = $matchedLineno - $totalBefore + $i;
				if ( !isset( $lines[ $lineno ] ) ) {
					$lines[$lineno] = [
						'lineno' => $lineno,
						'href' => $this->formatUrl( $repoConf, $rev, $path, $lineno ),
						'html' => htmlspecialchars( $text ),
						'isMatch' => false,
						'isMatchBoundary' => false,
					];
				}
			}
			foreach ( $match['After'] as $i => $text ) {
				$lineno = $matchedLineno + 1 + $i;
				if ( !isset( $lines[ $lineno ] ) ) {
					$lines[$lineno] = [
						'lineno' => $lineno,
						'href' => $this->formatUrl( $repoConf, $rev, $path, $lineno ),
						'html' => htmlspecialchars( $text ),
						'isMatch' => false,
						'isMatchBoundary' => false,
					];
				}
			}
		}

		usort( $lines, static function ( $a, $b ) {
			return $a['lineno'] - $b['lineno'];
		} );

		$prev = null;
		foreach ( $lines as &$line ) {
			if ( $prev !== null && ( $prev + 1 ) !== $line['lineno'] ) {
				$line['isMatchBoundary'] = true;
			}
			$prev = $line['lineno'];
		}

		return $lines;
	}

	private function makeHighlightedHtml( $text ) {
		@preg_match_all( '/' . strtr( $this->query, [ '/' => '\/' ] ) . '/',
			$text,
			$matches,
			PREG_OFFSET_CAPTURE
		);
		$html = '';
		$offset = 0;
		foreach ( $matches[0] ?? [] as $match ) {
			$html .= htmlspecialchars( substr( $text, $offset, $match[1] ) )
				. '<em>' . htmlspecialchars( $match[0] ) . '</em>';
			$offset = $match[1] + strlen( $match[0] );
		}
		return $html . htmlspecialchars( substr( $text, $offset ) );
	}

	private function processSearchResponse( array $repos, array $apiData ): array {
		$t = hrtime( true );
		// Example for `repos`
		// {   "MediaWiki core": {
		//         "url": "..",
		//         "url-pattern": {
		//             "base-url": "https://gerrit.wikimedia.org/g/mediawiki/core/+/{rev}/{path}{anchor}",
		//             "anchor": "#{line}"
		//         }
		//     }
		// }
		// Example for `apiData.Results`
		// {   "MyRepoName": {
		//           "Matches": [{
		//               "Filename": "example/file.txt",
		//               "Matches": [{
		//                   "Line": "A line with a matched word",
		//                   "LineNumber": 43,
		//                   "Before": ["Something", "Before"],
		//                   "After": ["And", "After"],
		//               }, ..]
		//           }, ..],
		//           "FilesWithMatch": 3,
		//           "Revision": "0ac66edf0a91d8687ce0e54d3af2944b3028ab1d"
		//     }
		// }

		$resultsKeyed = [];
		foreach ( $apiData['Results'] ?? [] as $repoId => $result ) {
			$repoConf = $repos[$repoId] ?? null;
			if ( $repoConf === null ) {
				throw new UnexpectedValueException( "Results for undefined repo $repoId" );
			}
			$matches = [];
			foreach ( $result['Matches'] as $match ) {
				$matches[] = [
					'filename' => $match['Filename'],
					'href' => $this->formatUrl( $repoConf, $result['Revision'], $match['Filename'], null ),
					'lines' => $this->flattenMatchesToLines( $match['Matches'],
						$repoConf, $result['Revision'], $match['Filename']
					)
				];
			}

			$hasMore = ( $result['FilesWithMatch'] > count( $matches ) );
			$moreSrc = $hasMore
				? './?' . http_build_query( [
					'action' => 'more',
					'repos' => $repoId,
				] + $this->getCanonicalFrontendQuery() )
				: null;

			$resultsKeyed[$repoId] = [
				'repoId' => $repoId,
				'matches' => $matches,
				'FilesWithMatch' => $result['FilesWithMatch'],
				'hasMore' => $hasMore,
				'moreSrc' => $moreSrc,
			];
		}

		// for format=Phabricator, sort ascending by repoId
		ksort( $resultsKeyed );
		$resultsAZ = array_values( $resultsKeyed );

		// for format=Default, sort by FilesWithMatch descending, then by repoId ascending
		$results = $resultsAZ;
		usort( $results, static function ( $a, $b ) {
			if ( $a['FilesWithMatch'] === $b['FilesWithMatch'] ) {
				return $a['repoId'] > $b['repoId'] ? 1 : -1;
			} else {
				return $b['FilesWithMatch'] - $a['FilesWithMatch'];
			}
		} );

		return [
			'Error' => $apiData['Error'] ?? null,
			'Stats' => $apiData['Stats'] ?? null,
			'renderDuration' => floor( ( hrtime( true ) - $t ) / 1e6 ),
			'hasResults' => (bool)$results,
			'results' => $results,
			'resultsAZ' => $resultsAZ,
		];
	}
}
