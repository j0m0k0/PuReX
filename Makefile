all: sort test

sort:
	uv tool run isort src/

test:
	uv tool run pytest
