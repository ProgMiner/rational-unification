
module M = Map.Make(Int)

type t = Term.t M.t

exception Occurs

let empty = M.empty

let rec walk s x = match M.find x.Term.n s with
| exception Not_found -> x, Term.Var x
| Term.Var x -> walk s x
| t -> x, t

let extend_no_check s x y = M.add x.Term.n y s

let rec occurs s x = function
| Term.Var y ->
    begin match walk s y with
    | y, _ when y.Term.r -> ()
    | y, _ when x.Term.n == y.Term.n -> raise Occurs
    | _, Term.Var _ -> ()
    | _, y -> occurs s x y
    end

| Term.Con (_, ts) -> Array.iter (occurs s x) ts

let extend s x y =
    if not x.Term.r then occurs s x y ;
    extend_no_check s x y

let union s x y =
    let x, xt = walk s x in
    let y, yt = walk s y in

    if x.Term.n == y.Term.n then s, None
    else begin
        let x, y, xt, yt =
            if
                if x.Term.r != y.Term.r
                then y.Term.r
                else x.Term.n > y.Term.n
            then x, y, xt, yt
            else y, x, yt, xt
        in

        match xt, yt with
        | Var _, Var _ -> extend_no_check s x yt, None
        | Var _, _ -> extend s x @@ Term.Var y, None
        | _, Var _ ->
            let s = extend s y xt in
            extend_no_check s x yt, None
        | _, _ -> extend s x @@ Term.Var y, Some (xt, yt)
    end

let rec unify_vt s x yt =
    let x, xt = walk s x in
    begin match xt with
    | Term.Var _ -> extend s x yt
    | _ ->
        let t = Term.common_part xt yt in
        let s = if t == xt then s else extend s x t in
        unify s xt yt
    end

and unify s xt yt =
    if xt == yt then s
    else match xt, yt with
    | Term.Var x, Term.Var y ->
        begin match union s x y with
        | s, Some (xt, yt) -> unify s xt yt
        | s, None -> s
        end

    | Term.Var x, _ -> unify_vt s x yt
    | _, Term.Var y -> unify_vt s y xt
    | Term.Con (f, ts1), Term.Con (g, ts2)
    when f == g && Array.length ts1 == Array.length ts2 ->
        let n = Array.length ts1 in

        let rec hlp i s =
            if i == n then s
            else hlp (i + 1) @@ unify s ts1.(i) ts2.(i)
        in

        hlp 0 s

    | _ -> raise Term.No_common_part
