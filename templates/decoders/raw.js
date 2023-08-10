function arrayToHex(stream) {
  return Array.from(stream, function(byte) {
      return ('0' + (byte & 0xFF).toString(16)).slice(-2);
  }).join('')
}

function decodeUplink(input) {
    return {
        data: [{'type': 255, 'name': 'raw', 'value': arrayToHex(input.bytes)}],
        warnings: [],
        errors: []
    };
}
