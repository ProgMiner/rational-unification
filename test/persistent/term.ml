
include Rational_unification.Persistent.Term

let var x = Var x
let con f ts = Con (f, ts)

let gen =
    let open QCheck.Gen in
    sized @@ fix @@ fun self n ->
        let hlp =
            let* k = int_bound 5 in

            if k = 0
            then return [||]
            else array_size (return k) (self @@ n / k)
        in

        if n = 0
        then map var nat
        else oneof_weighted
            [ 1, map var nat
            ; 2, map2 con nat hlp
            ]

let rec shrink =
    let open QCheck.Iter in
    let open QCheck.Shrink in
    function
    | Var x -> map var @@ int x
    | Con (f, ts) -> append_l
        [ map (fun f -> con f ts) @@ int f
        ; map (con f) @@ array ~shrink ts
        ]

let arbitrary = QCheck.make gen ~print:(Format.asprintf "%a" pp) ~shrink
