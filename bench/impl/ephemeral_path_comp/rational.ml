
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

let[@inline] is_cons x =
    let tx = Obj.tag x in
    Obj.first_non_constant_constructor_tag <= tx && tx <= Obj.last_non_constant_constructor_tag

module CommonPart = struct

    type side = Aside | Right | Left | Both

    let (<+>) x y = match x, y with
    | Both, _ -> y
    | _, Both -> x
    | Left, Left -> Left
    | Right, Right -> Right
    | _ -> Aside

    let rec common_part t1 t2 =
        if Var.check t1 && Var.check t2 then Both, t1
        else if Var.check t1 then Left, t1
        else if Var.check t2 then Right, t2
        else begin
            let tx = Obj.tag t1 in

            if tx != Obj.tag t2 then begin
                raise Common.Unification_failure
            end else begin
                if is_cons t1 then begin
                    let sx = Obj.size t1 in

                    if sx != Obj.size t2 then begin
                        raise Common.Unification_failure
                    end else begin
                        let res = Obj.dup t1 in 

                        let rec hlp i acc =
                            if i == sx then acc
                            else begin
                                let side, t = common_part (Obj.field t1 i) (Obj.field t2 i) in

                                Obj.set_field res i t ;
                                hlp (i + 1) @@ acc <+> side
                            end
                        in

                        match hlp 0 Both with
                        | Aside -> Aside, res
                        | Right -> Right, t2
                        | side -> side, t1
                    end
                end else begin
                    if t1 = t2 then Both, t1
                    else raise Common.Unification_failure
                end
            end
        end
end

let common_part x y = snd @@ CommonPart.common_part x y

let rec walk x = match x.Var.subst with
| None -> x, Obj.repr x
| Some t when Var.check t ->
    let y : Var.t = Obj.obj t in
    let y', _ as res = walk y in
    if y' != y then x.Var.subst <- Some (Obj.repr y') ;
    res
| Some t -> x, t

let union x y =
    let x, t1 = walk x in
    let y, t2 = walk y in

    if x == y then None
    else begin
        let x, y, t1, t2 =
            if x > y
            then x, y, t1, t2
            else y, x, t2, t1
        in

        if Var.check t1 && Var.check t2 then begin
            x.Var.subst <- Some t2 ;
            None
        end else if Var.check t1 then begin
            x.Var.subst <- Some (Obj.repr y) ;
            None
        end else if Var.check t2 then begin
            y.Var.subst <- Some t1 ;
            x.Var.subst <- Some t2 ;
            None
        end else begin
            x.Var.subst <- Some (Obj.repr y) ;
            Some (t1, t2)
        end
    end

let[@inline] rec unify_vt x t2 =
    let x, t1 = walk x in

    if Var.check t1 then begin
        x.Var.subst <- Some t2
    end else begin
        let t = common_part t1 t2 in
        if t != t1 then x.Var.subst <- Some t ;
        unify t1 t2
    end

and unify t1 t2 =
    if t1 == t2 then ()
    else if Var.check t1 && Var.check t2 then begin
        match union (Obj.obj t1 : Var.t) (Obj.obj t2 : Var.t) with
        | Some (t1, t2) -> unify t1 t2
        | None -> ()
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
                    for i = 0 to sx - 1 do
                        unify (Obj.field t1 i) (Obj.field t2 i)
                    done
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
    let cons tag xs = Obj.with_tag tag @@ Obj.repr (xs : t array)

    let rec size t =
        if Var.check t then 1
        else if is_cons t then begin
            let sx = Obj.size t in

            let rec hlp i acc =
                if i = sx then acc
                else hlp (i + 1) @@ acc + size (Obj.field t i)
            in

            hlp 0 1
        end else 1

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
