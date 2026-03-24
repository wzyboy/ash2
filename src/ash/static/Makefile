.PHONY: clean watch

main.css: clean
	sass scss/main.scss main.css --style compressed --embed-sources

watch:
	sass scss/main.scss main.css --style compressed --embed-sources --watch

clean:
	rm -rf main.css
