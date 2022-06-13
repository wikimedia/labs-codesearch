FROM php:8.1-apache-bullseye

RUN a2enmod rewrite

# Install libmustache
RUN apt-get update && apt-get install automake git libtool -y \
	&& git clone https://github.com/jbboehr/libmustache /tmp/libmustache \
	&& cd /tmp/libmustache \
	# Pin to specific commit, HEAD as of 2022-06-12
	&& git checkout 7605460febad8331469423b277b7b2cd1e934f18 \
	# Use HTTPS for submodule
	&& git submodule set-url spec "https://github.com/jbboehr/mustache-spec.git" \
	&& git submodule update --init \
	&& autoreconf -fiv && ./configure \
	&& make && make install && cd / && rm -rf /tmp/libmustache \
	&& apt-get remove automake git libtool -y && apt autoremove -y

# https://pecl.php.net/package/mustache
RUN pecl install mustache-0.9.2 \
	&& docker-php-ext-enable mustache

# https://pecl.php.net/package/APCu
RUN pecl install apcu-5.1.21 \
	&& docker-php-ext-enable apcu

COPY . /var/www/html/
