<?php
// phpcs:disable MediaWiki.Usage.SuperGlobalsUsage

use Wikimedia\Codesearch\Codesearch;

require_once __DIR__ . '/vendor/autoload.php';

// Use ?forceprofile=1 to generate a trace log, written to speedscope-*.json
// https://www.mediawiki.org/wiki/Excimer
if ( isset( $_GET['forceprofile'] ) && extension_loaded( 'excimer' ) ) {
	$excimer = new ExcimerProfiler();
	$excimer->setPeriod( 0.001 ); // 1ms
	$excimer->setEventType( EXCIMER_REAL );
	$excimer->start();
	register_shutdown_function( static function () use ( $excimer ) {
		$excimer->stop();
		$data = $excimer->getLog()->getSpeedscopeData();
		$data['profiles'][0]['name'] = $_SERVER['REQUEST_URI'];
		$action = preg_replace( '/[^a-zA-Z0-9]+/', '', $_GET['action'] ?? 'search' );
		file_put_contents( __DIR__ . '/trace-' . gmdate( 'Ymd\THis\Z' ) . "-$action.speedscope.json",
				json_encode( $data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) );
		Codesearch::debug( 'Saved Excimer trace ' );
	} );
}

$search = new Codesearch();

$model = new Wikimedia\Codesearch\Model( $search );

try {
	$resp = $model
		->setURL( $_SERVER['REQUEST_URI'] )
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
