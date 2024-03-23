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

class Model {
	private const ACTIONS = [
		'search',
		'repos',
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

	public function execute(): Response {
		$response = new Response();

		// Maintain a clean (but Hound-compatible) URL
		// Don't include "repos" here, because it does not translate to other backends.
		$canonicalFrontendQueryString = http_build_query( [
			'q' => $this->query !== '' ? $this->query : null,
			'i' => $this->caseInsensitive ? 'fosho' : null,
			'files' => $this->filePath !== '' ? $this->filePath : null,
			'excludeFiles' => $this->excludeFiles !== '' ? $this->excludeFiles : null,
		] );
		// Avoid dangling "?" by itself
		$canonicalFrontendQueryString = $canonicalFrontendQueryString ? "?$canonicalFrontendQueryString" : '';

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

		$isSubmit = ( $this->query !== '' );
		$apiQueryUrl = $isSubmit
			? $this->search->formatApiQueryUrl( $this->backend, $fields )
			: null;

		$jsData = [
			'reposData' => $reposData,
			'apiQueryUrl' => $apiQueryUrl,
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
			'isSubmit' => $isSubmit,
			'doctitle' => $isSubmit ? $this->query : null,
			'apiQueryUrl' => $apiQueryUrl,
			'backendLabel' => $label,
			'backends' => $backends,
			'fields' => $fields,
			'selectedRepoCount' => strval( count( $selectedRepos ) ?: '' ),
			'jsDataRawHtml' => $jsDataRawHtml,
		] );
		return $response;
	}
}
