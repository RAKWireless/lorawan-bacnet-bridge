function decode(bytes) {

    // The output of the decoder should be a list of objects, each object is a data measurement.
    // Each object should have a 'type', a 'name' and a current 'value'.
    // Check cayenne.js for a list of supported data types.

    return [
        {'type': 103, 'name': 'temperature', 'value': 23.7},
        {'type': 136, 'name': 'gps', 'value': {'latitude': 41.42, 'longitude': 2.17, 'altitude': 20}}
    ]

}

// The entrypoint method has the same signature as that for The Things Stack v3
function decodeUplink(input) {

    bytes = input.bytes;
    fPort = input.fPort;

    return {
      data: decode(bytes),
      warnings: [],
      errors: []
    };
    
}
