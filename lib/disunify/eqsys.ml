
module M = Map.Make(Int)

type t = Term.t M.t
type prefix = (int * Term.t) list

let empty = M.empty

let rec walk s x = match M.find x s with
| exception Not_found -> x, Term.Var x
| Term.Var x -> walk s x
| t -> x, t

type union_outcome =
| Same
| Extend of int * Term.t
| Unify of Term.t * Term.t

let union s x y =
    let x, xt = walk s x in
    let y, yt = walk s y in

    if x == y then s, Same
    else begin
        let x, y, xt, yt =
            if x > y
            then x, y, xt, yt
            else y, x, yt, xt
        in

        match xt, yt with
        | Var _, Var _ -> M.add x yt s, Extend (x, yt)
        | Var _, _ -> M.add x (Term.Var y) s, Extend (x, yt)
        | _, Var _ ->
            let s = M.add y xt s in
            M.add x yt s, Extend (y, xt)
        | _, _ -> M.add x (Term.Var y) s, Unify (xt, yt)
    end

let rec unify_vt s acc x yt =
    let x, xt = walk s x in
    begin match xt with
    | Term.Var _ -> M.add x yt s, (x, yt)::acc
    | _ ->
        let t = Term.common_part xt yt in
        let s = if t == xt then s else M.add x t s in
        unify s acc xt yt
    end

and unify s acc xt yt =
    if xt == yt then s, acc
    else match xt, yt with
    | Term.Var x, Term.Var y ->
        begin match union s x y with
        | s, Unify (xt, yt) -> unify s acc xt yt
        | s, Extend (x, yt) -> s, (x, yt)::acc
        | s, Same -> s, acc
        end

    | Term.Var x, _ -> unify_vt s acc x yt
    | _, Term.Var y -> unify_vt s acc y xt
    | Term.Con (f, ts1), Term.Con (g, ts2)
    when f == g && Array.length ts1 == Array.length ts2 ->
        let n = Array.length ts1 in

        let rec hlp i (s, acc) =
            if i == n then s, acc
            else hlp (i + 1) @@ unify s acc ts1.(i) ts2.(i)
        in

        hlp 0 (s, acc)

    | _ -> raise Term.No_common_part

let unify s x y = unify s [] x y

let unify_prefix s p =
    let xs = Array.of_list @@ List.map (fun (x, _) -> Term.Var x) p in
    let ys = Array.of_list @@ List.map snd p in
    unify s (Term.Con (0, xs)) (Term.Con (0, ys))
