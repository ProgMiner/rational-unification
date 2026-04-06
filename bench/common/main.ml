
module type Term = Term.S
module Trace = Trace.Make

module Config = struct

    type t = {
        mutable trace_file: string;
        mutable check: bool;
        mutable cpu: int;
        mutable warmup: int;
        mutable samples: int;
        mutable iters: int;
        mutable quiet: bool;
    }

    let default () = {
        trace_file = "" ;
        check = false ;
        cpu = 0 ;
        warmup = 100 ;
        samples = 100 ;
        iters = 100 ;
        quiet = false ;
    }

    let parse () =
        let res = default () in

        let trace_file_set = ref false in
        let add_trace_file filename =
            if !trace_file_set then begin
                raise @@ Arg.Bad (Printf.sprintf "trace file is already defined (%s)" res.trace_file)
            end ;

            res.trace_file <- filename ;
            trace_file_set := true
        in

        let arg_spec = Arg.[
            "--check", Unit (fun () -> res.check <- true), "only print state dump after single run" ;
            "--cpu", Int (fun x -> res.cpu <- x), "set preferred CPU to run" ;
            "--warmup", Int (fun x -> res.warmup <- x), "number of warm-up iterations" ;
            "--samples", Int (fun x -> res.samples <- x), "number of samples" ;
            "--iters", Int (fun x -> res.iters <- x), "number of iterations per sample" ;
            "--quiet", Unit (fun () -> res.quiet <- true), "don't emit human-readable logs" ;
        ] in

        let cmd_name = Sys.argv.(0) in
        let usage = Printf.sprintf "Usage: %s [options] <trace file>" cmd_name in
        Arg.parse arg_spec add_trace_file usage ;

        if not !trace_file_set then begin
            Printf.eprintf "%s: trace file not set.\n" cmd_name ;
            Arg.usage arg_spec usage ;
            exit 0
        end ;

        res
end

module Make(T : Term) = struct

    module Trace = Trace(T)

    let single_run trace =
        List.fold_left (fun st (t1, t2) -> T.unify st t1 t2) (T.initial_state ()) trace

    let pp_state_dump ppf xs =
        xs |> Hashtbl.iter begin fun x t ->
            Format.fprintf ppf "  %d -> %a\n" x T.pp t
        end

    let[@inline][@specialise] main () =
        let cfg = Config.parse () in

        if Array.length Sys.argv < 1 then begin
            Printf.printf "Usage: %s <trace file>\n" Sys.argv.(0) ;
            exit 0
        end ;

        Power.pin_cpu cfg.Config.cpu ;
        Power.check_governor cfg.Config.cpu ;

        if cfg.Config.check then begin
            let trace = Trace.unmarshal_from_file cfg.Config.trace_file in
            let dump = T.dump_state @@ single_run trace in

            begin
                if cfg.Config.quiet then Format.printf "%a" pp_state_dump dump
                else Format.printf "State dump:\n%a" pp_state_dump dump
            end ;

            exit 0
        end ;

        if not cfg.Config.quiet then begin
            Printf.printf "Warm-up...\n" ;
            flush stdout
        end ;

        for _ = 1 to cfg.Config.warmup do
            let trace = Trace.unmarshal_from_file cfg.Config.trace_file in
            Sys.opaque_identity (ignore @@ single_run trace)
        done ;

        if not cfg.Config.quiet then begin
            Printf.printf "Samples (ns):\n" ;
            flush stdout
        end ;

        for i = 1 to cfg.Config.samples do
            Gc.full_major () ;

            let span = ref Mtime.Span.zero in

            for _ = 1 to cfg.Config.iters do
                let trace = Trace.unmarshal_from_file cfg.Config.trace_file in

                let counter = Mtime_clock.counter () in
                Sys.opaque_identity (ignore @@ single_run trace) ;
                span := Mtime.Span.add !span @@ Mtime_clock.count counter
            done ;

            let sample = Mtime.Span.to_float_ns !span /. float_of_int cfg.Config.iters in
            Printf.printf "%d\t%.1f\n" i sample ;
            flush stdout
        done
end
