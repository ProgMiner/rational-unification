
let rec common_part x y = match x, y with
| Term.Var _, _ -> x
| _, Term.Var _ -> y
| Term.Con (f, ts1), Term.Con (g, ts2) when f == g && Array.length ts1 == Array.length ts2 ->
    Term.Con (f, Array.map2 common_part ts1 ts2)
| _ -> raise Term.No_common_part

let rec assert_common_part x y z = match x, y with
| Term.Var _, Term.Var _ -> if x <> z && y <> z then invalid_arg "wrong common part"
| Term.Var _, _ -> if x <> z then invalid_arg "wrong common part"
| _, Term.Var _ -> if y <> z then invalid_arg "wrong common part"
| Term.Con (f, ts1), Term.Con (g, ts2) when f == g && Array.length ts1 == Array.length ts2 ->
    begin match z with
    | Term.Con (h, ts3) when f == h && Array.length ts1 == Array.length ts3 ->
        Array.map2 assert_common_part ts1 ts2 |> Array.iter2 (|>) ts3
    | _ -> invalid_arg "wrong common part"
    end
| _ -> raise Term.No_common_part

let is_common_part x y z =
    try assert_common_part x y z ; true
    with Invalid_argument _ -> false

let arbitrary_common_part =
    let gen =
        let open QCheck.Gen in
        
        let rec hlp = function
        | Term.Var _ as x ->
            let* t = Term.gen in
            let* side = bool in

            if side
            then return (x, t)
            else return (t, x)

        | Term.Con (f, ts) ->
            let ts = Array.map hlp ts in
            let* ts = flatten_array ts in
            let ts1, ts2 = Array.split ts in
            return (Term.Con (f, ts1), Term.Con (f, ts2))
        in

        let* t = Term.gen in
        hlp t
    in

    QCheck.set_gen gen @@ QCheck.pair Term.arbitrary Term.arbitrary

let test_success (x, y) =
    let z = Term.common_part x y in
    is_common_part x y z && begin
        if x = y then x == z || y == z
        else if x = z then x == z
        else if y = z then y == z
        else true
    end

let test_success =
    let open QCheck in
    Test.make ~count:100 ~name:"common part success" arbitrary_common_part test_success

let test_failure (x, y) =
    begin
        try let _ = common_part x y in QCheck.assume_fail ()
        with Term.No_common_part -> ()
    end ;

    try let _ = Term.common_part x y in false
    with Term.No_common_part -> true

let test_failure =
    let open QCheck in
    let arbitrary = pair Term.arbitrary Term.arbitrary in
    Test.make ~count:100 ~name:"common part failure" arbitrary test_failure

let test_refl x = Term.common_part x x == x

let test_refl =
    let open QCheck in
    Test.make ~count:100 ~name:"common part reflexivity" Term.arbitrary test_refl

let test_sym (x, y) = is_common_part x y @@ Term.common_part y x

let test_sym =
    let open QCheck in
    Test.make ~count:100 ~name:"common part symmetry" arbitrary_common_part test_sym

let () = QCheck.Test.check_exn test_success
let () = QCheck.Test.check_exn test_failure
let () = QCheck.Test.check_exn test_refl
let () = QCheck.Test.check_exn test_sym
