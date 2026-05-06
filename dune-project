(lang dune 3.19)

(name rational-unification)

(generate_opam_files true)

(source
 (github username/reponame))

(authors "Author Name <author@example.com>")

(maintainers "Maintainer Name <maintainer@example.com>")

(license LICENSE)

(documentation https://url/to/documentation)

(package
 (name rational-unification)
 (synopsis "A short synopsis")
 (description "A longer description")
 (depends
   (ocaml (>= 5))
   (qcheck (and :with-test (>= 0.90)))
   (mtime (>= 2))
   processor
   benchmark)
 (tags
  ("add topics" "to describe" your project)))

; See the complete stanza docs at https://dune.readthedocs.io/en/stable/reference/dune-project/index.html
