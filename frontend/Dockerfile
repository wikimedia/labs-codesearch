FROM php:8.1-apache-bullseye

RUN a2enmod rewrite

# https://pecl.php.net/package/APCu
RUN pecl install apcu-5.1.21 \
	&& docker-php-ext-enable apcu

COPY . /var/www/html/
