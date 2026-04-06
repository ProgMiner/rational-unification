
type t
type prefix = (int * Term.t) list

val empty : t

val unify : t -> Term.t -> Term.t -> t * prefix

val unify_prefix : t -> prefix -> t * prefix
