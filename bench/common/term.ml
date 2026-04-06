
module type S = sig

    type t
    type state

    val var : int -> t
    val int : int -> t
    val float : float -> t
    val string : string -> t
    val cons : int -> t array -> t

    val pp : Format.formatter -> t -> unit

    val initial_state : unit -> state
    val dump_state : state -> (int, t) Hashtbl.t

    val unify : state -> t -> t -> state
end
