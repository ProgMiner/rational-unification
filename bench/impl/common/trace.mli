
module Make(T : Term.S) : sig

    val unmarshal_term : in_channel -> T.t
    
    val unmarshal : in_channel -> (T.t * T.t) list
    val unmarshal_from_file : string -> (T.t * T.t) list
end
