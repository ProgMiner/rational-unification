
module Var : sig

    type anchor

    type t = {
        anchor: anchor;
        index: int;
        mutable subst: Obj.t option;
    }

    val make : int -> t
    val check : Obj.t -> bool
end = struct

    type anchor = int ref
    let anchor = ref 1337

    type t = {
        anchor: anchor;
        index: int;
        mutable subst: Obj.t option;
    }

    let make index = { anchor ; index ; subst = None }

    let my_tag, my_size =
        let dummy = Obj.repr (make 0 : t) in
        Obj.tag dummy, Obj.size dummy

    let[@inline] check x =
        Obj.tag x == my_tag && Obj.size x == my_size && (Obj.obj x).anchor == anchor
end

let walk =
    let rec walkv x = match x.Var.subst with
    | None -> Obj.repr x
    | Some t -> walkt t

    and walkt t =
        if Var.check t
        then walkv (Obj.obj t : Var.t)
        else t
    in

    walkv

let[@inline] is_cons x =
    let tx = Obj.tag x in
    Obj.first_non_constant_constructor_tag <= tx && tx <= Obj.last_non_constant_constructor_tag

let link_cons x y = Obj.set_field x 0 y

let rec deref_cons x =
    let x' = Obj.field x 0 in
    if Obj.tag x' == Obj.int_tag then x
    else deref_cons x'

let[@inline] rec unify_vt x t2 =
    let t1 = walk x in

    if Var.check t1 then begin
        let x : Var.t = Obj.obj t1 in
        x.Var.subst <- Some t2
    end else begin
        unify t1 t2
    end

and unify t1 t2 =
    if t1 == t2 then ()
    else if Var.check t1 && Var.check t2 then begin
        let t1 = walk (Obj.obj t1 : Var.t) in
        let t2 = walk (Obj.obj t2 : Var.t) in

        if Var.check t1 && Var.check t2 then begin
            let x : Var.t = Obj.obj t1 in
            let y : Var.t = Obj.obj t2 in

            if x == y then ()
            else if x.Var.index < y.Var.index then y.Var.subst <- Some t1
            else x.Var.subst <- Some t2
        end else if Var.check t1 then begin
            let x : Var.t = Obj.obj t1 in
            x.Var.subst <- Some t2
        end else if Var.check t2 then begin
            let y : Var.t = Obj.obj t2 in
            y.Var.subst <- Some t1
        end else begin
            unify t1 t2
        end
    end else if Var.check t1 then begin
        unify_vt (Obj.obj t1 : Var.t) t2
    end else if Var.check t2 then begin
        unify_vt (Obj.obj t2 : Var.t) t1
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
                    let t1 = deref_cons t1 in
                    let t2 = deref_cons t2 in

                    if t1 == t2 then ()
                    else begin
                        link_cons t1 t2 ;

                        for i = 1 to sx - 1 do
                            unify (Obj.field t1 i) (Obj.field t2 i)
                        done
                    end
                end
            end else begin
                if t1 <> t2 then begin
                    raise Common.Unification_failure
                end
            end
        end
    end

module Term = struct

    type t = Obj.t
    type state = (int, Var.t) Hashtbl.t

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
    let cons tag xs =
        let n = Array.length xs in
        let res = Obj.new_block tag (n + 1) in
        for i = 0 to n - 1 do
            Obj.set_field res (i + 1) @@ Obj.repr xs.(i)
        done ;
        res

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

    let initial_state () =
        let res = Hashtbl.rebuild vars in
        Hashtbl.clear vars ;
        res

    let dump_state vars =
        let res = Hashtbl.create @@ Hashtbl.length vars in
        vars |> Hashtbl.iter begin fun _ x ->
            match x.Var.subst with
            | Some t -> Hashtbl.add res x.Var.index t
            | None -> ()
        end ;
        res

    let unify st t1 t2 =
        unify t1 t2 ;
        st
end

let () = Common.main (module Term)
