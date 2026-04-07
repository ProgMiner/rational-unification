

module type Term = Term.S

module Int64_IO : sig

    val input : in_channel -> int64
end = struct

    let buf = Bytes.create 8

    let input chan =
        really_input chan buf 0 8 ;
        Bytes.get_int64_le buf 0
end

let input_int64 = Int64_IO.input

module Make(T : Term) = struct

    let rec unmarshal_term chan =
        match input_byte chan with
        | 0 -> T.var @@ Int64.to_int @@ input_int64 chan
        | 1 -> T.int @@ Int64.to_int @@ input_int64 chan
        | 2 -> T.float @@ Int64.float_of_bits @@ input_int64 chan
        | 3 ->
            let length = Int64.to_int @@ input_int64 chan in
            T.string @@ Option.get @@ In_channel.really_input_string chan length
        | 4 ->
            let tx = Int64.to_int @@ input_int64 chan in
            let sx = Int64.to_int @@ input_int64 chan in
            let xs = Array.make sx @@ Obj.magic 0 in
            for i = 0 to sx - 1 do
                xs.(i) <- unmarshal_term chan
            done ;
            T.cons tx xs
        | x -> invalid_arg @@ Printf.sprintf "Trace.unmarshal_term: incorrect data (%d)" x
    
    let[@tail_mod_cons] rec unmarshal chan =
        match unmarshal_term chan with
        | exception End_of_file -> []
        | t1 ->
            let t2 = unmarshal_term chan in
            (t1, t2) :: unmarshal chan
    
    let unmarshal_from_file filename =
        In_channel.with_open_bin filename unmarshal
end
