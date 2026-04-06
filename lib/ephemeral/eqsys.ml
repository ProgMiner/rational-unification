
let rec walk x = match x.Term.s with
| None -> x, Term.Var x
| Some (Term.Var x) -> walk x
| Some t -> x, t

let union x y =
    let x, xt = walk x in
    let y, yt = walk y in

    if x == y then None
    else begin
        let x, y, xt, yt =
            if x > y
            then x, y, xt, yt
            else y, x, yt, xt
        in

        match xt, yt with
        | Var _, Var _ -> x.Term.s <- Some yt ; None
        | Var _, _ -> x.Term.s <- Some (Term.Var y) ; None
        | _, Var _ -> y.Term.s <- Some xt ; x.Term.s <- Some yt ; None
        | _, _ -> x.Term.s <- Some (Term.Var y) ; Some (xt, yt)
    end

let rec unify_vt x yt =
    let x, xt = walk x in
    begin match xt with
    | Term.Var _ -> x.Term.s <- Some yt
    | _ ->
        let t = Term.common_part xt yt in
        if t != xt then x.Term.s <- Some t ;
        unify xt yt
    end

and unify xt yt =
    if xt == yt then ()
    else match xt, yt with
    | Term.Var x, Term.Var y ->
        begin match union x y with
        | Some (xt, yt) -> unify xt yt
        | None -> ()
        end

    | Term.Var x, _ -> unify_vt x yt
    | _, Term.Var y -> unify_vt y xt
    | Term.Con (f, ts1), Term.Con (g, ts2)
    when f == g && Array.length ts1 == Array.length ts2 ->
        Array.iter2 unify ts1 ts2

    | _ -> raise Term.No_common_part
