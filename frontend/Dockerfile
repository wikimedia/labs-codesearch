FROM php:8.3-apache-bookworm

RUN a2enmod rewrite

# Install libmustache
RUN apt-get update && apt-get install automake git libtool -y \
	&& git clone https://github.com/jbboehr/libmustache /tmp/libmustache \
	&& cd /tmp/libmustache \
	# Pin to specific commit, HEAD as of 2024-04-08
	&& git checkout 4f003a4620994e8817a8d8088acbae3ffd072726 \
	# Use HTTPS for submodule
	&& git submodule set-url spec "https://github.com/jbboehr/mustache-spec.git" \
	&& git submodule update --init \
	&& autoreconf -fiv && ./configure \
	&& make && make install && cd / && rm -rf /tmp/libmustache \
	&& apt-get remove automake git libtool -y && apt-get autoremove -y

# TODO: If we end up using Composer for things other than autoload
# Install php-zip, required by Composer
# RUN apt-get install -y libzip-dev zip && docker-php-ext-install zip

# https://pecl.php.net/package/mustache
RUN pecl install mustache-0.9.3 \
	&& docker-php-ext-enable mustache

# https://pecl.php.net/package/APCu
RUN pecl install apcu-5.1.23 \
	&& docker-php-ext-enable apcu

# PHP settings
# - Opcache is off by default. https://hub.docker.com/_/php/
# - https://www.php.net/manual/en/opcache.configuration.php
RUN echo "zend_extension=opcache" >> "$PHP_INI_DIR/php.ini"
RUN echo "opcache.validate_timestamps=0" >> "$PHP_INI_DIR/php.ini"
# - Default memory_limit is 128M
RUN echo "memory_limit=128M" >> "$PHP_INI_DIR/php.ini"

# Install composer
RUN mkdir /srv/composer \
	&& cd /srv/composer \
	&& curl --silent --fail --output composer.phar https://getcomposer.org/download/2.3.3/composer.phar \
	&& chmod +x /srv/composer/composer.phar \
	&& mv /srv/composer/composer.phar /usr/bin/composer

COPY . /var/www/html/

RUN find /var/www/html/static -type f -print0 | xargs -0 sha1sum | sort | sha1sum | head -c 7 > /var/www/html/staticversion.txt

# This is basically just to set up a PSR-4 autoloader.
# (In Docker mode we use native PECL mustache, instead of the Composer package.)
USER nobody
RUN cd /var/www/html/ \
	&& rm -rf /var/www/html/vendor \
	&& /usr/bin/composer dump-autoload -a

USER root
