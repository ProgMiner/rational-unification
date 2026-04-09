
module Var : sig

    type anchor

    type t = {
        anchor: anchor;
        index: int;
    }

    val make : int -> t
    val check : Obj.t -> bool
end = struct

    type anchor = int ref
    let anchor = ref 1337

    type t = {
        anchor: anchor;
        index: int;
    }

    let make index = { anchor ; index }

    let my_tag, my_size =
        let dummy = Obj.repr (make 0 : t) in
        Obj.tag dummy, Obj.size dummy

    let[@inline] check x =
        Obj.tag x == my_tag && Obj.size x == my_size && (Obj.obj x).anchor == anchor
end

module IM = Map.Make(Int)

let walk s =
    let rec walkv x = match IM.find x.Var.index s with
    | exception Not_found -> Obj.repr x
    | t -> walkt t

    and walkt t =
        if Var.check t
        then walkv (Obj.obj t : Var.t)
        else t
    in

    walkv

let[@inline] is_cons x =
    let tx = Obj.tag x in
    Obj.first_non_constant_constructor_tag <= tx && tx <= Obj.last_non_constant_constructor_tag

let link_cons s x y = IM.add (Obj.obj @@ Obj.field x 0 : int) y s

let rec deref_cons s x =
    match IM.find (Obj.obj @@ Obj.field x 0 : int) s with
    | exception Not_found -> x
    | x -> deref_cons s x

let[@inline] rec unify_vt s x t2 =
    let t1 = walk s x in

    if Var.check t1 then begin
        let x : Var.t = Obj.obj t1 in
        IM.add x.Var.index t2 s
    end else begin
        unify s t1 t2
    end

and unify s t1 t2 =
    if t1 == t2 then s
    else if Var.check t1 && Var.check t2 then begin
        let t1 = walk s (Obj.obj t1 : Var.t) in
        let t2 = walk s (Obj.obj t2 : Var.t) in

        if Var.check t1 && Var.check t2 then begin
            let x : Var.t = Obj.obj t1 in
            let y : Var.t = Obj.obj t2 in

            if x == y then s
            else if x.Var.index < y.Var.index then IM.add y.Var.index t1 s
            else IM.add x.Var.index t2 s
        end else if Var.check t1 then begin
            let x : Var.t = Obj.obj t1 in
            IM.add x.Var.index t2 s
        end else if Var.check t2 then begin
            let y : Var.t = Obj.obj t2 in
            IM.add y.Var.index t1 s
        end else begin
            unify s t1 t2
        end
    end else if Var.check t1 then begin
        unify_vt s (Obj.obj t1 : Var.t) t2
    end else if Var.check t2 then begin
        unify_vt s (Obj.obj t2 : Var.t) t1
    end else begin
        let tx = Obj.tag t1 in

        if tx != Obj.tag t2 then begin
            raise Common.Unification_failure
        end else begin
            if is_cons t1 then begin
                let sx = Obj.size t1 in

                if sx != Obj.size t2 then begin
                    raise Common.Unification_failure
                end else begin
                    let t1 = deref_cons s t1 in
                    let t2 = deref_cons s t2 in

                    if t1 == t2 then s
                    else begin
                        let s = link_cons s t1 t2 in

                        let rec hlp i s =
                            if i == sx then s
                            else unify s (Obj.field t1 i) (Obj.field t2 i) |> hlp (i + 1)
                        in

                        hlp 1 s
                    end
                end
            end else begin
                if t1 = t2 then s
                else begin
                    raise Common.Unification_failure
                end
            end
        end
    end

module Term = struct

    type t = Obj.t
    type state = t IM.t

    let vars : (int, Var.t) Hashtbl.t = Hashtbl.create 8
    let cons_idx = ref 0

    let var index =
        if index < 0 then invalid_arg "Term.var: negative indexes aren't supported" ;

        match Hashtbl.find vars index with
        | res -> Obj.repr res
        | exception Not_found ->
            let res = Var.make index in
            Hashtbl.add vars index res ;
            Obj.repr res

    let int x = Obj.repr (x : int)
    let float x = Obj.repr (x : float)
    let string x = Obj.repr (x : string)
    let cons tag xs =
        let n = Array.length xs in
        let res = Obj.new_block tag (n + 1) in
        for i = 0 to n - 1 do
            Obj.set_field res (i + 1) @@ Obj.repr xs.(i)
        done ;
        decr cons_idx ;
        Obj.set_field res 0 @@ Obj.repr (!cons_idx : int) ;
        res

    let rec size t =
        if Var.check t then 1
        else if is_cons t then begin
            let sx = Obj.size t in

            let rec hlp i acc =
                if i = sx then acc
                else hlp (i + 1) @@ acc + size (Obj.field t i)
            in

            hlp 1 1
        end else 1

    let rec pp ppf t =
        if Var.check t then begin
            let x : Var.t = Obj.obj t in
            Format.fprintf ppf "_%d" x.Var.index
        end else begin
            let tx = Obj.tag t in

            if is_cons t then begin
                Format.fprintf ppf "boxed %d <" tx ;
                for i = 1 to Obj.size t - 1 do
                    if i > 1 then Format.fprintf ppf ", " ;
                    pp ppf @@ Obj.field t i
                done ;
                Format.fprintf ppf ">"
            end else if tx == Obj.int_tag then begin
                Format.fprintf ppf "int<%d>" (Obj.obj t : int)
            end else if tx == Obj.double_tag then begin
                Format.fprintf ppf "double<%e>" (Obj.obj t : float)
            end else if tx == Obj.string_tag then begin
                Format.fprintf ppf "string<%s>" (Obj.obj t : string)
            end
        end

    let initial_state () = IM.empty

    let dump_state s =
        let res = Hashtbl.create @@ IM.cardinal s in
        s |> IM.iter begin fun x t ->
            if x >= 0 then Hashtbl.add res x t
        end ;
        res

    let unify = unify
end

let () = Common.main (module Term)
