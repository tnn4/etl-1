# .PHONY is a special directive in a Makefile that tells make: "The targets listed here are abstract commands, not physical files on disk."
.PHONY: all etl test test-e2e serve

etl:
	uv run scripts/run_all_etl_pipelines.py

test:
	uv run pytest -m "not e2e"

test-e2e:
	uv run pytest

serve:
	python3 -m http.server 8000

# Remove temporary SQLite artifacts or local test caches
clean:
	rm -rf .pytest_cache public/data/weather_table.db

all:
	etl test test-e2e serve