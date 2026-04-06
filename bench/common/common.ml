
module type Term = Term.S
module Trace = Trace.Make

exception Unification_failure

let[@inline][@specialise] main (module T : Term) =
    let module Main = Main.Make(T) in
    Main.main ()
