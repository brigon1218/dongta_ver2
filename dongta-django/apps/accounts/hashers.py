import hashlib
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.crypto import constant_time_compare


class LegacyMD5PasswordHasher(BasePasswordHasher):
    """
    PHP 레거시 md5 해시를 지원하는 커스텀 해셔.
    형식: md5$<hash>
    """
    algorithm = "md5"

    def encode(self, password, salt):
        """
        신규 패스워드 저장 시에는 이 해셔를 사용하지 않음.
        (Django 기본 해셔인 Argon2id/BCrypt가 사용됨)
        """
        assert password is not None
        hash = hashlib.md5(password.encode()).hexdigest()
        return f"{self.algorithm}${hash}"

    def verify(self, password, encoded):
        """
        md5$<hash> 형식의 데이터를 검증.
        """
        algorithm, hash = encoded.split('$', 1)
        assert algorithm == self.algorithm
        encoded_2 = self.encode(password, None)
        return constant_time_compare(encoded, encoded_2)

    def safe_summary(self, encoded):
        algorithm, hash = encoded.split('$', 1)
        assert algorithm == self.algorithm
        return {
            'algorithm': algorithm,
            'hash': mask_hash(hash, show=3),
        }

    def decode(self, encoded):
        algorithm, hash = encoded.split('$', 1)
        return {
            'algorithm': algorithm,
            'hash': hash,
        }
