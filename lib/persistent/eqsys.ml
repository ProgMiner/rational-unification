
module M = Map.Make(Int)

type t = Term.t M.t

let empty = M.empty

let rec walk s x = match M.find x s with
| exception Not_found -> x, Term.Var x
| Term.Var x -> walk s x
| t -> x, t

(*
(* straightforward implementation *)
let union s x y =
    let x, xt = walk s x in
    let y, yt = walk s y in

    if x == y then s, None
    else begin match xt, yt with
    | Var _, Var _ -> M.add x yt s, None
    | Var _, _ -> M.add x (Term.Var y) s, None
    | _, Var _ -> M.add y (Term.Var x) s, None
    | _, _ -> M.add x (Term.Var y) s, Some (xt, yt)
    end
*)

(* with variable age heuristic *)
let union s x y =
    let x, xt = walk s x in
    let y, yt = walk s y in

    if x == y then s, None
    else begin
        let x, y, xt, yt =
            if x > y
            then x, y, xt, yt
            else y, x, yt, xt
        in

        match xt, yt with
        | Var _, Var _ -> M.add x yt s, None
        | Var _, _ -> M.add x (Term.Var y) s, None
        | _, Var _ ->
            let s = M.add y xt s in
            M.add x yt s, None
        | _, _ -> M.add x (Term.Var y) s, Some (xt, yt)
    end

(*
(* with common part *)
let union s x y =
    let x, xt = walk s x in
    let y, yt = walk s y in

    if x == y then s, None
    else begin
        let x, y, xt, yt =
            if x > y
            then x, y, xt, yt
            else y, x, yt, xt
        in

        match xt, yt with
        | Var _, Var _ -> M.add x yt s, None
        | Var _, _ -> M.add x (Term.Var y) s, None
        | _, Var _ ->
            let s = M.add y xt s in
            M.add x yt s, None
        | _, _ ->
            let s = M.add y (Term.common_part xt yt) s in
            M.add x (Term.Var y) s, Some (xt, yt)
    end
*)

let rec unify_vt s x yt =
    let x, xt = walk s x in
    begin match xt with
    | Term.Var _ -> M.add x yt s
    | _ ->
        let t = Term.common_part xt yt in
        let s = if t == xt then s else M.add x t s in
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
