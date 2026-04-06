
module M = Map.Make(Int)

type store = Eqsys.prefix list M.t

type state = {
    s: Eqsys.t;
    c: store;
}

exception Disunification_violated

let record_constraint st x p = { st with c = M.add_to_list x p st.c }

let recheck_constraint st p = match Eqsys.unify_prefix st.s p with
| _, ((x, _)::_ as p) -> record_constraint st x p
| _, [] -> raise Disunification_violated
| exception Term.No_common_part -> st

let recheck st x = match M.find x st.c with
| c -> List.fold_left recheck_constraint { st with c = M.remove x st.c } c
| exception Not_found -> st

let recheck_prefix = List.fold_left @@ fun st (x, t) ->
    let st = recheck st x in
    match t with
    | Term.Var y -> recheck st y
    | _ -> st

let unify st x y =
    let s, p = Eqsys.unify st.s x y in
    recheck_prefix { st with s } p

let disunify st x y = match Eqsys.unify st.s x y with
| _, ((x, _)::_ as p) -> record_constraint st x p
| _, [] -> raise Disunification_violated
| exception Term.No_common_part -> st
