
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

let rec occurs s x t =
    if Var.check t then begin
        let t = walk s (Obj.obj t : Var.t) in
        if Var.check t then begin
            let y : Var.t = Obj.obj t in
            if x == y then raise Common.Unification_failure
        end else occurs s x t
    end else if is_cons t then begin
        for i = 0 to Obj.size t - 1 do
            occurs s x @@ Obj.field t i
        done
    end

let extend s x t =
    occurs s x t ;
    IM.add x.Var.index t s

let[@inline] rec unify_vt s x t2 =
    let t1 = walk s x in

    if Var.check t1 then begin
        let x : Var.t = Obj.obj t1 in
        extend s x t2
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
            extend s x t2
        end else if Var.check t2 then begin
            let y : Var.t = Obj.obj t2 in
            extend s y t1
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
                    let rec hlp i s =
                        if i == sx then s
                        else unify s (Obj.field t1 i) (Obj.field t2 i) |> hlp (i + 1)
                    in

                    hlp 0 s
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

    let var index =
        match Hashtbl.find vars index with
        | res -> Obj.repr res
        | exception Not_found ->
            let res = Var.make index in
            Hashtbl.add vars index res ;
            Obj.repr res

    let int x = Obj.repr (x : int)
    let float x = Obj.repr (x : float)
    let string x = Obj.repr (x : string)
    let cons tag xs = Obj.with_tag tag @@ Obj.repr (xs : t array)

    let rec pp ppf t =
        if Var.check t then begin
            let x : Var.t = Obj.obj t in
            Format.fprintf ppf "_%d" x.Var.index
        end else begin
            let tx = Obj.tag t in

            if is_cons t then begin
                Format.fprintf ppf "boxed %d <" tx ;
                for i = 0 to Obj.size t - 1 do
                    if i > 0 then Format.fprintf ppf ", " ;
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
            Hashtbl.add res x t
        end ;
        res

    let unify = unify
end

let () = Common.main (module Term)
