

let pin_cpu cpu =
    try Processor.Affinity.set_ids [cpu]
    with Unix.Unix_error (_, msg, _) -> 
        Printf.eprintf "!!! Unable to pin CPU %d (%s) !!!\n" cpu msg

let read_file path = In_channel.with_open_bin path In_channel.input_all

let check_governor cpu =
    let path = Printf.sprintf "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor" cpu in

    match read_file path with
    | governor ->
        if String.trim governor <> "performance" then begin
            Printf.eprintf "!!! Seems like CPU %d power governor is not \"performance\" (but \"%s\") !!!\n"
                cpu @@ String.escaped governor
        end

    | exception Sys_error msg ->
        Printf.eprintf "!!! Unable to check CPU %d power governor (%s) !!!\n" cpu msg
