<?php
$cfg = require __DIR__ . '/../vendor/mediawiki/mediawiki-phan-config/src/config.php';
$cfg['minimum_target_php_version'] = '8.1';
$cfg['directory_list'][] = 'vendor/';
$cfg['exclude_analysis_directory_list'][] = 'vendor/';

return $cfg;
