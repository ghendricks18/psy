# -*- coding: utf-8 -*-
#
#  Cipher/PKCS1-v1_5.py : PKCS#1 v1.5
#
# ===================================================================
# The contents of this file are dedicated to the public domain.  To
# the extent that dedication to the public domain is not available,
# everyone is granted a worldwide, perpetual, royalty-free,
# non-exclusive license to exercise all rights associated with the
# contents of this file for any purpose whatsoever.
# No rights are reserved.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ===================================================================

"""RSA encryption protocol according to PKCS#1 v1.5

See RFC3447 or the `original RSA Labs specification`__ .

This scheme is more properly called ``RSAES-PKCS1-v1_5``.

**If you are designing a new protocol, consider using the more robust PKCS#1 OAEP.**

As an example, a sender may encrypt a message in this way:

        >>> from Crypto.Cipher import PKCS1_v1_5
        >>> from Crypto.PublicKey import RSA
        >>> from Crypto.Hash import SHA
        >>> from Crypto import Random
        >>>
        >>> rng = Random.new()
        >>> message = 'To be encrypted'
        >>> h = SHA.new(message)
        >>> key = RSA.importKey(open('pubkey.der').read())
        >>> ciphertext = PKCS1_v1_5.encrypt(message+h.digest(), key, rng.read)

At the receiver side, decryption can be done using the private part of
the RSA key:

        >>> From Crypto.Hash import SHA
        >>> from Crypto import Random
        >>>
        >>> rng = Random.new()
        >>> dsize = SHA.digest_size
        >>> key = RSA.importKey(open('privkey.der').read())
        >>> sentinel = Random.new().read(15+dsize)      # Let's assume that average data length is 15
        >>> message = PKCS1_v1_5.decrypt(ciphertext, key, sentinel)
        >>> digest = SHA.new(message[:-dsize]).digest()
        >>> if digest==message[-dsize:]:                # Note how we DO NOT look for the sentinel
        >>>     print "Encryption was correct."
        >>> else:
        >>>     print "Encryption was not correct."

.. __: http://www.rsa.com/rsalabs/node.asp?id=2125.
"""

__revision__ = "$Id$"
__all__ = [ 'encrypt', 'decrypt' ]

from Crypto.Util.number import ceil_div
import Crypto.Util.number

def encrypt(message, key, randFunc):
    """Produce the PKCS#1 v1.5 encryption of a message.

    This function is named ``RSAES-PKCS1-V1_5-ENCRYPT``, and is specified in
    section 7.2.1 of RFC3447.

    :Parameters:
     message : string
            The message to encrypt, also known as plaintext. It can be of
            variable length, but not longer than the RSA modulus (in bytes) minus 11.
     key : RSA key object
            The key to use to encrypt the message. This is a `Crypto.PublicKey.RSA`
            object.
     randFunc : callable
            An RNG function that accepts as only parameter an integer, and returns
            a string of random bytes.

    :Return: A string, the ciphertext in which the message is encrypted.
        It is as long as the RSA modulus (in bytes).
    :Raise ValueError:
        If the RSA key length is not sufficiently long to deal with the given
        message.
    """
    # TODO: Verify the key is RSA

    # See 7.2.1 in RFC3447
    modBits = Crypto.Util.number.size(key.n)
    k = ceil_div(modBits,8) # Convert from bits to bytes
    mLen = len(message)

    # Step 1
    if mLen > k-11:
        raise ValueError("Plaintext is too long.")
    # Step 2a
    class nonZeroRandByte:
        def __init__(self, rf): self.rf=rf
        def __call__(self, c):
            while c=='\x00': c=self.rf(1)
            return c
    ps = "".join(map(nonZeroRandByte(randFunc), randFunc(k-mLen-3)))
    # Step 2b
    em = '\x00\x02' + ps + '\x00' + message
    # Step 3a (OS2IP), step 3b (RSAEP), part of step 3c (I2OSP)
    m = key.encrypt(em, 0)[0]
    # Complete step 3c (I2OSP)
    c = '\x00'*(k-len(m)) + m
    return c

def decrypt(ct, key, sentinel):
    """Decrypt a PKCS#1 v1.5 ciphertext.

    This function is named ``RSAES-PKCS1-V1_5-DECRYPT``, and is specified in
    section 7.2.2 of RFC3447.

    :Parameters:
     ct : string
            The ciphertext that contains the message to recover.
     key : RSA key object
            The key to use to verify the message. This is a `Crypto.PublicKey.RSA`
            object. It must have its private half.
     sentinel : string
            The string to return to indicate that an error was detected during decryption.

    :Return: A string, the original message or the ``sentinel``.
    :Raise ValueError:
        If the ciphertext length is incorrect
    :Raise TypeError:
        If the RSA key has no private half.

    :attention:
        You should **never** let the party who submitted the ciphertext know that
        this function returned the ``sentinel`` value, since attacks exist (e.g. `Bleichenbacher's`__)
        that can compromise your RSA private key by means of such information.

        In general, it should not be possible for the other party to distinguish
        whether processing at the server side failed because the value returned
        was a ``sentinel`` as opposed to a random, invalid message.
        
        In fact, the second option is not that unlikely: encryption done according to PKCS#1 v1.5
        embeds no good integrity check. There is roughly one chance
        in 2^16 for a random ciphertext to be returned as a valid message
        (although random looking).

        It is therefore advisabled to:

        1. Select as ``sentinel`` a value that resembles a plausable random, invalid message.
        2. Not report back an error as soon as you detect a ``sentinel`` value.
           Put differently, you should not explicitly check if the returned value is the ``sentinel`` or not.
        3. Cover all possible errors with a single, generic error indicator.
        4. Embed into the definition of ``message`` (at the protocol level) a digest (e.g. ``SHA-1``).
        5. Where possible, monitor the number of errors due to ciphertexts originating from the same party,
           and slow down the rate of the requests from such party (or even blacklist it altogether).
 
        **If you are designing a new protocol, consider using the more robust PKCS#1 OAEP.**

        .. __: http://www.springerlink.com/index/j5758n240017h867.pdf
    """

    # TODO: Verify the key is RSA

    # See 7.2.1 in RFC3447
    modBits = Crypto.Util.number.size(key.n)
    k = ceil_div(modBits,8) # Convert from bits to bytes

    # Step 1
    if len(ct) != k:
        raise ValueError("Ciphertext with incorrect length.")
    # Step 2a (O2SIP), 2b (RSADP), and part of 2c (I2OSP)
    m = key.decrypt(ct)
    # Complete step 2c (I2OSP)
    em = '\x00'*(k-len(m)) + m
    # Step 3
    sep = em.find('\x00',2)
    if  not em.startswith('\x00\x02') or sep<10:
        return sentinel
    # Step 4
    return em[sep+1:]

