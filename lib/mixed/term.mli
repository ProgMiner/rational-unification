
type var = {
    n: int;
    r: bool;
}

type t =
| Var of var
| Con of int * t array

val pp : Format.formatter -> t -> unit

exception No_common_part

val common_part : t -> t -> t
