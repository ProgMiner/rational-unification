
type t =
| Var of int
| Con of int * t array

let rec pp ppf = function
| Var x -> Format.fprintf ppf "x_%d" x
| Con (c, [||]) -> Format.fprintf ppf "c_%d" c
| Con (f, ts) ->
    Format.fprintf ppf "f_%d(%a" f pp ts.(0) ;
    for i = 1 to Array.length ts - 1 do
        Format.fprintf ppf ", %a" pp ts.(i)
    done ;
    Format.fprintf ppf ")"

exception No_common_part

(*
(* straightforward implementation *)
let rec common_part x y = match x, y with
| Var x, _ -> Var x
| _, Var y -> Var y
| Con (f, ts1), Con (g, ts2)
when f == g && Array.length ts1 == Array.length ts2 ->
    Con (f, Array.map2 common_part ts1 ts2)
| _ -> raise No_common_part
*)

module CommonPart = struct

    type side = Aside | Right | Left | Both

    let (<+>) x y = match x, y with
    | Both, _ -> y
    | _, Both -> x
    | Left, Left -> Left
    | Right, Right -> Right
    | _ -> Aside

    let rec common_part x y = match x, y with
    | Var _, Var _ -> Both, x
    | Var _, _ -> Left, x
    | _, Var _ -> Right, y
    | Con (f, ts1), Con (g, ts2) when f == g && Array.length ts1 == Array.length ts2 ->
        let n = Array.length ts1 in

        let ts = Array.make n (Var 0) in
        let rec hlp i acc = if i == n then acc else
            let side, ti = common_part ts1.(i) ts2.(i) in

            ts.(i) <- ti ;
            hlp (i + 1) @@ acc <+> side
        in

        begin match hlp 0 Both with
        | Aside -> Aside, Con (f, ts)
        | Right -> Right, y
        | side -> side, x
        end

    | _ -> raise No_common_part
end

let common_part x y = snd @@ CommonPart.common_part x y
