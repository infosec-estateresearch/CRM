<?php

namespace Espo\Custom\Hooks\Account;

use Espo\Core\Hook\Hook\BeforeRemove;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;

/**
 * CRM-IDINT-001R: identity integrity for Account (BeforeRemove). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 */
class IdentityBeforeRemove implements BeforeRemove
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function beforeRemove(Entity $entity, RemoveOptions $options): void
    {
        $this->guard->beforeRemove($entity);
    }
}
