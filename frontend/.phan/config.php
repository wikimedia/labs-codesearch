<?php
$cfg = require __DIR__ . '/../vendor/mediawiki/mediawiki-phan-config/src/config.php';
$cfg['minimum_target_php_version'] = '8.1';
$cfg['autoload_internal_extension_signatures'] = [
	'mustache' => '.phan/internal_stubs/mustache.phan_php',
];
$cfg['directory_list'] = [
	'vendor/',
	'src/',
];
$cfg['exclude_analysis_directory_list'][] = 'vendor/';

return $cfg;
