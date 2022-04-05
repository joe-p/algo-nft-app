CLEAN_TESTS="rm -f tests/*.teal tests/index.js* tests/dryruns/*"

test:
	eval ${CLEAN_TESTS}
	cd tests && ../contract.py && npx tsc && npx jest

clean:
	rm -f *.teal
	eval ${CLEAN_TESTS}

teal: 
	python3 contract.py

lint:
	cd tests && npx eslint index.ts

fix:
	cd tests && npx eslint index.ts --fix

init:
	cd tests && mkdir -p dryruns && npm i
