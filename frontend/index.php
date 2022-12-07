<?php

require_once __DIR__ . '/vendor/autoload.php';

$search = new Wikimedia\Codesearch\Codesearch();

$model = new Wikimedia\Codesearch\Model( $search );

try {
	$resp = $model
		->setURL( $_SERVER['REQUEST_URI'] )
		// phpcs:ignore MediaWiki.Usage.SuperGlobalsUsage.SuperGlobals
		->setGetParams( $_GET )
		->execute();
} catch ( Throwable $e ) {
	$resp = new Wikimedia\Codesearch\Response(
		500,
		[],
		new Wikimedia\Codesearch\View( 'error', [
			'doctitle' => 'Internal error',
			'error' => get_class( $e ) . ': ' . $e->getMessage(),
			'trace' => $e->getTraceAsString(),
		] )
	);
}

$resp->send();
