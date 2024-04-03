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

	/**
	 * Generate optional query string for URLs to the /static/ directory.
	 *
	 * This is used to ensure integrity between requests around deployments,
	 * and to ensure natural cache invalidation. For example, if a commit
	 * changes both HTML and CSS/JavaScript such that one depends on something
	 * new in the other, then this ensures we don't use outdated browser cache
	 * for a CSS/JS response in combination with a new server response HTML.
	 *
	 * Context: https://gerrit.wikimedia.org/r/c/labs/codesearch/+/898238
	 *
	 * This method is written in loving memory of MediaWiki's $wgStyleVersion
	 * (https://phabricator.wikimedia.org/T181318).
	 *
	 * @return string Query string
	 */
	private function getStaticUrlQuery(): string {
		if ( !function_exists( 'apcu_fetch' ) ) {
			return '';
		}
		$key = 'codesearch-staticversion-v1';
		$version = apcu_fetch( $key );
		if ( !$version ) {
			// phpcs:ignore Generic.PHP.NoSilencedErrors.Discouraged
			$version = @file_get_contents( __DIR__ . '/../staticversion.txt' ) ?: 'dev';
			// Safe to keep maximally in apcu because staticversion.txt is written
			// at container build time. Changes naturally result in server restarts.
			apcu_store( $key, $version, 0 );
		}
		return '?' . $version;
	}

	private function getSharedData(): array {
		return [
			'staticversion' => $this->getStaticUrlQuery(),
		];
	}

	public function getExtraHeaders(): array {
		$staticversion = $this->getStaticUrlQuery();
		$preloads = implode( ',', [
			"</static/lib/bootstrap-5.1.3/bootstrap.min.css>;rel=preload;as=style",
			"</static/styles.css$staticversion>;rel=preload;as=style",
		] );
		return [
			"Link: $preloads"
		];
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

		return $mustache->render( $templateContent, $this->data + $this->getSharedData() );
	}
}
