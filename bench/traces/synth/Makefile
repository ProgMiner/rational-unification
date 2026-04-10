
N=100
K=10

SETS=full left_right

.PHONY: all clean
.SUFFIXES:

all: $(SETS)

clean:
	-rm -rvf $(SETS)

%: %.py
	mkdir "$@"
	for (( i = 0; i <= $N; i += 10 )); do "./$<" "$$i" >"$@/n$$i.trace"; done
