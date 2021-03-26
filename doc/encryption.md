Since v3.00 the encryption for passwords is made a bit stronger.

Until this version all that was done was a simple base64 hash. Now, real encryption in implemented, with keys and auto key rotation.
To enable this, use zbxdb.py -g to generate an encryption key.
The zbxdb.py monitors the keysdir where the keys will be generated (default next to the used cfg file with
name "keys/")
As soon as there is a change in the keysdir, zbxdb.py will detect that and restart itself. During the
initialisation the password will be rekeyed.

Basically there is one keysdir that is the same for all .cfg files but if you want you can have multiple
keysdirs ...... Easiest is just one ....

Be sure not to loose the keys, no decryption is possible without them.

Although the keys provide a strong encryption, you might want to rotate the key every once and a while, for example if someone left the company. With
your zbxdb.py processes running, just generate a new key and within a few minutes all processes will rekey
their password_enc in their .cfg file. If you are sure that all instances of zbxdb.py that used a specific
key has rekeyed them, the old key can be deleted.


check password: zbxdb.py -c {your}.cfg -p password
This will decode the password_enc using the all keys and methods until if fallsback to the base64 hash.
