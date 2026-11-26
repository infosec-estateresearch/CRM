<?php

namespace Espo\Custom\Hooks\Account;

use Espo\Core\Hook\Hook\BeforeMassRelate;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001: identity integrity for Account (BeforeMassRelate). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 *
 * @implements BeforeMassRelate<Entity>
 */
class IdentityBeforeMassRelate implements BeforeMassRelate
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function beforeMassRelate(Entity $entity, string $relationName, mixed ...$rest): void
    {
        $this->guard->beforeMassRelate($entity, $relationName);
    }
}
