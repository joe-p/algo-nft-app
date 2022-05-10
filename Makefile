CLEAN_TESTS="rm -f tests/*.teal tests/index.js* tests/dryruns/*"

test:
	eval ${CLEAN_TESTS}
	cd tests && cp ../*.teal . && npx tsc && npx jest

clean:
	rm -f *.teal
	eval ${CLEAN_TESTS}

teal: 
	ruby contract.rb

lint:
	cd tests && npx eslint index.ts
	rubocop || true

fix:
	cd tests && npx eslint index.ts --fix
	rubocop -a

init:
	cd tests && mkdir -p dryruns && npm i
