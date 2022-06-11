<?php
if ( PHP_SAPI !== 'cli-server' ) {
	die( 'Invalid invocation.' );
}

$file = $_SERVER['SCRIPT_FILENAME'] ?? '';
$uri = $_SERVER['REQUEST_URI'] ?? '/';
$uriPathExt = pathinfo( $uri, PATHINFO_EXTENSION );

// Scenarios:
//
// 1. The request URL path refers to a PHP or static file that exists.
//    Value: Absolute file path as translated from request URL.
//    Default behaviour: Serve or execute the file accordingly.
//
// 2. The request URL path contains a dot in the last part, but no file exists.
//    Value: Relative URL path to the router file (this file).
//    Default behaviour: 404 Not Found.
//
// 3. Anything else, e.g. URL paths that are directories (existing or not)
//    and paths without final slash that are extension-less and don't exist.
//    Value: {docroot}/index.php
//    Default behaviour: Render index.php.

if (
	// Default for error
	!$file ||
	// Default for non-existent file
	( $uriPathExt !== '' && !is_file( $file ) ) ||
	// Default for addressed PHP file
	( $uriPathExt === 'php' ) ||
	// Default for static file
	( $uriPathExt !== '' && $uriPathExt !== 'php' )
) {
	return false;
}

$rewrites = [
	// Document root, optional query
	'/^\/?(\?.*)?$/' => __DIR__ . '/../index.php',
	// Top-level virtual path, optional query
	'/^\/?[0-9a-z]+\/?(\?.*)?$/' => __DIR__ . '/../index.php',
];
foreach ( $rewrites as $pattern => $dest ) {
	if ( preg_match( $pattern, $uri ) ) {
		require $dest;
		return true;
	}
}

http_response_code( 404 );
header( 'Content-Type: text/plain; charset=utf-8' );
// @phan-suppress-next-line SecurityCheck-XSS
echo "Not Found: $uri\n";
return true;
