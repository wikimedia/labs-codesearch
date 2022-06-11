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
	private string $backend = '';
	private string $query = '';
	private bool $caseInsensitive = false;
	private string $filePath = '';
	private string $excludeFilePath = '';
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

	public function setExcludeFilePath( string $excludeFilePath ): self {
		$this->excludeFilePath = $excludeFilePath;
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
		$canonicalFrontendQueryString = '?' . http_build_query( [
			'q' => $this->query !== '' ? $this->query : null,
			'i' => $this->caseInsensitive ? 'fosho' : null,
			'files' => $this->filePath !== '' ? $this->filePath : null,
			'excludeFilePath' => $this->excludeFilePath !== '' ? $this->excludeFilePath : null,
		] );

		if ( $this->backend === '' ) {
			// Redirect to default backend
			$response->statusCode = 301;
			$response->headers[] =
				'Location: /' . Codesearch::BACKEND_DEFAULT . "/$canonicalFrontendQueryString";
			return $response;
		}

		$backends = [];
		foreach ( Codesearch::BACKENDS as $id => $label ) {
			$backends[] = [
				'href' => "/$id/$canonicalFrontendQueryString",
				'label' => $label,
				'active' => $id === $this->backend,
			];
		}

		if ( !$this->search->isValidBackend( $this->backend ) ) {
			$response->statusCode = 404;
			$error = "Unknown search backend \"{$this->backend}\".";
			$response->view = new View( 'error', [
				'doctitle' => 'Not found',
				'error' => $error,
				'backends' => $backends,
			] );
			return $response;
		}

		$repoData = $this->search->getCachedConfig( $this->backend );

		$selectedRepos = explode( ',', $this->repos );
		$selectedRepos = array_intersect( $selectedRepos, array_keys( $repoData ) );
		$repos = implode( ',', $selectedRepos );

		$fields = [
			'query' => $this->query,
			'caseInsensitive' => $this->caseInsensitive,
			'filePath' => $this->filePath,
			'excludeFilePath' => $this->excludeFilePath,
			'repos' => $repos,
		];

		$isSubmit = ( $this->query !== '' );
		$apiQueryUrl = $isSubmit
			? $this->search->formatApiQueryUrl( $this->backend, $fields )
			: null;

		$jsData = [
			'reposData' => $repoData,
			'apiQueryUrl' => $apiQueryUrl,
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
			'backends' => $backends,
			'fields' => $fields,
			'selectedRepoCount' => strval( count( $selectedRepos ) ?: '' ),
			'jsDataRawHtml' => $jsDataRawHtml,
		] );
		return $response;
	}
}
