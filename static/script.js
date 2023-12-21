// script.js
document.addEventListener('DOMContentLoaded', function () {
    // Read the token from the cookie
    var token = document.cookie.split('; ').find(row => row.startsWith('token=')).split('=')[1];

    // Store the token in sessionStorage
    sessionStorage.setItem('token', token);
});
