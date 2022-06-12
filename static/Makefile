.PHONY: clean watch

main.css: clean
	sass scss/main.scss main.css --style compressed

clean:
	rm -rf main.css

watch:
	sass scss/main.scss main.css --style compressed --watch
